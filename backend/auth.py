from __future__ import annotations

import html
import re
from datetime import datetime, timedelta
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from pymongo import MongoClient

from backend.core.config import settings
from backend.email_service import app_base_url, send_activation_email, send_password_reset_email
from backend.security import hash_password, hash_token, make_token, verify_password

USERS_COLLECTION = "Users"
SESSION_KEY = "auth_user"

_client = MongoClient(settings.MONGO_URI)
_db = _client[settings.DB_NAME]
_users_col = _db[USERS_COLLECTION]


def utcnow() -> datetime:
    return datetime.utcnow()


def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


def _serialize_user(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc.get("_id")),
        "name": doc.get("Name") or doc.get("name") or "",
        "email": doc.get("Email") or doc.get("email") or "",
        "role": doc.get("Rol") or doc.get("role") or "",
        "status": doc.get("Status") or doc.get("status") or "active",
        "configsId": [str(v) for v in (doc.get("Configs_Id") or doc.get("configs_id") or [])],
    }


def find_user_by_email(email: str) -> dict[str, Any] | None:
    email = _norm_email(email)
    if not email:
        return None
    return _users_col.find_one({"Email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}})


def _find_user_for_login(username_or_email: str) -> dict[str, Any] | None:
    value = (username_or_email or "").strip()
    if not value:
        return None
    return _users_col.find_one({
        "$or": [
            {"Name": {"$regex": f"^{re.escape(value)}$", "$options": "i"}},
            {"Email": {"$regex": f"^{re.escape(value)}$", "$options": "i"}},
        ]
    })


def _password_matches_and_migrate(doc: dict[str, Any], password: str) -> bool:
    stored_hash = doc.get("PasswordHash") or doc.get("password_hash")
    if stored_hash and verify_password(password, stored_hash):
        return True
    legacy = doc.get("Password")
    if legacy and legacy == password:
        _users_col.update_one({"_id": doc["_id"]}, {"$set": {"PasswordHash": hash_password(password), "updated_at": utcnow()}})
        return True
    return False


def authenticate_user_status(username: str, password: str) -> dict[str, Any]:
    username = (username or "").strip()
    password = (password or "").strip()
    if not username or not password:
        return {"ok": False, "reason": "invalid"}

    doc = _find_user_for_login(username)
    if not doc or not _password_matches_and_migrate(doc, password):
        return {"ok": False, "reason": "invalid"}

    status = (doc.get("Status") or doc.get("status") or "active").strip().lower()
    if status != "active":
        return {"ok": False, "reason": "inactive", "email": doc.get("Email") or "", "name": doc.get("Name") or ""}

    return {"ok": True, "user": _serialize_user(doc)}


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    result = authenticate_user_status(username, password)
    return result.get("user") if result.get("ok") else None


def current_user(request: Request) -> dict[str, Any] | None:
    user = request.session.get(SESSION_KEY)
    return user if isinstance(user, dict) and user.get("role") else None


def is_admin(user: dict[str, Any] | None) -> bool:
    role = ((user or {}).get("role") or "").strip().lower()
    return role in {"admin", "superadmin", "super_admin", "super admin"}


def is_client(user: dict[str, Any] | None) -> bool:
    role = ((user or {}).get("role") or "").strip().lower()
    return role in {"cliente", "client", "visitor", "visitante"}


def landing_for(user: dict[str, Any] | None) -> str:
    if is_admin(user):
        return "/"
    return "/metricas"


def create_activation_for_user(doc: dict[str, Any]) -> str:
    token = make_token()
    _users_col.update_one({"_id": doc["_id"]}, {"$set": {
        "activation_token_hash": hash_token(token),
        "activation_expires_at": utcnow() + timedelta(hours=24),
        "updated_at": utcnow(),
    }})
    return token


def send_activation_for_user(doc: dict[str, Any]) -> None:
    token = create_activation_for_user(doc)
    url = f"{app_base_url()}/activate?token={token}"
    send_activation_email(doc.get("Email") or "", doc.get("Name") or "", url)


def create_inactive_client_user(name: str, email: str, password: str) -> tuple[bool, str, dict[str, Any] | None]:
    name = (name or "").strip()
    email = _norm_email(email)
    password = password or ""
    if not name:
        return False, "Name is required.", None
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return False, "A valid email is required.", None
    if len(password) < 8:
        return False, "Password must be at least 8 characters.", None
    if find_user_by_email(email):
        return False, "An account with this email already exists.", None

    doc = {
        "Name": name,
        "Email": email,
        "PasswordHash": hash_password(password),
        "Rol": "Cliente",
        "Status": "inactive",
        "Configs_Id": [],
        "email_verified_at": None,
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    res = _users_col.insert_one(doc)
    doc["_id"] = res.inserted_id
    send_activation_for_user(doc)
    return True, "Account created. Please check your email.", doc


def activate_user_by_token(token: str) -> dict[str, Any] | None:
    token_hash = hash_token(token or "")
    doc = _users_col.find_one({"activation_token_hash": token_hash})
    if not doc:
        return None
    expires = doc.get("activation_expires_at")
    if expires and expires < utcnow():
        return None
    _users_col.update_one({"_id": doc["_id"]}, {"$set": {
        "Status": "active",
        "email_verified_at": utcnow(),
        "updated_at": utcnow(),
    }, "$unset": {"activation_token_hash": "", "activation_expires_at": ""}})
    doc.update({"Status": "active", "email_verified_at": utcnow()})
    return _serialize_user(doc)


def create_password_reset(email: str) -> None:
    doc = find_user_by_email(email)
    if not doc:
        return
    token = make_token()
    _users_col.update_one({"_id": doc["_id"]}, {"$set": {
        "reset_token_hash": hash_token(token),
        "reset_expires_at": utcnow() + timedelta(hours=1),
        "updated_at": utcnow(),
    }})
    url = f"{app_base_url()}/reset-password?token={token}"
    send_password_reset_email(doc.get("Email") or "", doc.get("Name") or "", url)


def reset_password_by_token(token: str, password: str) -> tuple[bool, str]:
    if len(password or "") < 8:
        return False, "Password must be at least 8 characters."
    doc = _users_col.find_one({"reset_token_hash": hash_token(token or "")})
    if not doc:
        return False, "Invalid or expired reset link."
    expires = doc.get("reset_expires_at")
    if expires and expires < utcnow():
        return False, "Invalid or expired reset link."
    _users_col.update_one({"_id": doc["_id"]}, {"$set": {"PasswordHash": hash_password(password), "updated_at": utcnow()}, "$unset": {"reset_token_hash": "", "reset_expires_at": ""}})
    return True, "Password updated. You can sign in now."


def _page(title: str, subtitle: str, inner_html: str, error: str = "", success: str = "") -> HTMLResponse:
    error_html = f'<div class="error">{html.escape(error)}</div>' if error else ""
    success_html = f'<div class="success">{html.escape(success)}</div>' if success else ""
    return HTMLResponse(f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><title>{html.escape(title)} | Meta Tool</title>
<style>
:root{{color-scheme:dark}}*{{box-sizing:border-box;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#0b0d11;color:#e5e7eb}}.card{{width:min(460px,calc(100vw - 32px));background:#12151c;border:1px solid #1e2230;border-radius:18px;padding:28px;box-shadow:0 24px 80px rgba(0,0,0,.35)}}h1{{margin:0 0 6px;font-size:24px}}p{{margin:0 0 20px;color:#9ca3af;font-size:14px;line-height:1.5}}label{{display:block;font-size:12px;font-weight:700;color:#9ca3af;text-transform:uppercase;letter-spacing:.06em;margin:14px 0 6px}}input{{width:100%;background:#0b0d11;color:#fff;border:1px solid #263044;border-radius:10px;padding:12px 14px;font-size:15px;outline:none}}input:focus{{border-color:#3b82f6;box-shadow:0 0 0 3px rgba(59,130,246,.18)}}button{{width:100%;margin-top:20px;border:0;border-radius:10px;padding:12px 14px;background:#3b82f6;color:white;font-weight:800;cursor:pointer}}button:hover{{filter:brightness(1.08)}}.error{{background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.35);color:#fecaca;padding:10px 12px;border-radius:10px;font-size:13px;margin-bottom:14px}}.success{{background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.35);color:#bbf7d0;padding:10px 12px;border-radius:10px;font-size:13px;margin-bottom:14px}}.brand{{display:flex;align-items:center;gap:10px;margin-bottom:20px;color:#60a5fa;font-weight:900}}.dot{{width:12px;height:12px;border-radius:50%;background:#3b82f6;box-shadow:0 0 24px #3b82f6}}a{{color:#60a5fa;text-decoration:none}}a:hover{{text-decoration:underline}}.links{{display:flex;justify-content:space-between;gap:12px;margin-top:14px;font-size:13px}}.muted{{color:#94a3b8;font-size:13px;margin-top:16px}}
</style></head><body><div class="card"><div class="brand"><span class="dot"></span><span>Meta Tool</span></div><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p>{error_html}{success_html}{inner_html}</div></body></html>""")


def login_page(error: str = "") -> HTMLResponse:
    return _page("Iniciar sesión", "Ingresa con tu usuario/correo y contraseña.", """
<form method="post" action="/login">
<label for="username">Usuario o correo</label><input id="username" name="username" autocomplete="username" required autofocus />
<label for="password">Contraseña</label><input id="password" name="password" type="password" autocomplete="current-password" required />
<button type="submit">Entrar</button>
<div class="links"><a href="/register">Crear cuenta</a><a href="/forgot-password">Forgot password?</a></div>
</form>""", error=error)


def register_page(error: str = "") -> HTMLResponse:
    return _page("Crear cuenta", "Regístrate para acceder al dashboard de métricas.", """
<form method="post" action="/register">
<label>Nombre</label><input name="name" required autofocus />
<label>Correo</label><input name="email" type="email" autocomplete="email" required />
<label>Contraseña</label><input name="password" type="password" autocomplete="new-password" minlength="8" required />
<label>Confirmar contraseña</label><input name="password_confirm" type="password" autocomplete="new-password" minlength="8" required />
<button type="submit">Crear cuenta</button>
<div class="links"><a href="/login">Ya tengo cuenta</a></div>
</form>""", error=error)


def activate_account_page(email: str = "", message: str = "") -> HTMLResponse:
    safe_email = html.escape(email or "")
    return _page("Activate your account", "Check your email and click the activation link to continue.", f"""
<div class="success">{html.escape(message or 'We sent an activation email. Please check your inbox.')}</div>
<form method="post" action="/activate-account/resend">
<label>Correo</label><input name="email" type="email" value="{safe_email}" required />
<button type="submit">Resend activation email</button>
<div class="links"><a href="/login">Back to login</a></div>
</form>""")


def forgot_password_page(error: str = "", success: str = "") -> HTMLResponse:
    return _page("Forgot password", "Enter your email and we will send reset instructions.", """
<form method="post" action="/forgot-password">
<label>Correo</label><input name="email" type="email" autocomplete="email" required autofocus />
<button type="submit">Send reset link</button>
<div class="links"><a href="/login">Back to login</a></div>
</form>""", error=error, success=success)


def reset_password_page(token: str = "", error: str = "") -> HTMLResponse:
    safe_token = html.escape(token or "", quote=True)
    return _page("Reset password", "Choose a new password for your account.", f"""
<form method="post" action="/reset-password">
<input type="hidden" name="token" value="{safe_token}" />
<label>Nueva contraseña</label><input name="password" type="password" autocomplete="new-password" minlength="8" required autofocus />
<label>Confirmar contraseña</label><input name="password_confirm" type="password" autocomplete="new-password" minlength="8" required />
<button type="submit">Update password</button>
</form>""", error=error)
