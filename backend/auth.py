from __future__ import annotations

import html
import re
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from pymongo import MongoClient

from backend.core.config import settings

USERS_COLLECTION = "Users"
SESSION_KEY = "auth_user"

_client = MongoClient(settings.MONGO_URI)
_db = _client[settings.DB_NAME]
_users_col = _db[USERS_COLLECTION]


def _serialize_user(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc.get("_id")),
        "name": doc.get("Name") or doc.get("name") or "",
        "role": doc.get("Rol") or doc.get("role") or "",
        "configsId": [str(v) for v in (doc.get("Configs_Id") or doc.get("configs_id") or [])],
    }


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    username = (username or "").strip()
    password = (password or "").strip()
    if not username or not password:
        return None

    doc = _users_col.find_one(
        {
            "Name": {"$regex": f"^{re.escape(username)}$", "$options": "i"},
            "Password": password,
        }
    )
    if not doc:
        return None
    return _serialize_user(doc)


def current_user(request: Request) -> dict[str, Any] | None:
    user = request.session.get(SESSION_KEY)
    return user if isinstance(user, dict) and user.get("role") else None


def is_admin(user: dict[str, Any] | None) -> bool:
    return ((user or {}).get("role") or "").strip().lower() == "admin"


def is_client(user: dict[str, Any] | None) -> bool:
    role = ((user or {}).get("role") or "").strip().lower()
    return role in {"cliente", "client", "visitor", "visitante"}


def landing_for(user: dict[str, Any] | None) -> str:
    if is_admin(user):
        return "/"
    return "/metricas"


def login_page(error: str = "") -> HTMLResponse:
    safe_error = html.escape(error or "")
    error_html = f'<div class="error">{safe_error}</div>' if safe_error else ""
    return HTMLResponse(
        f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Login | Meta Tool</title>
  <style>
    :root {{ color-scheme: dark; }}
    * {{ box-sizing: border-box; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
    body {{ margin:0; min-height:100vh; display:grid; place-items:center; background:#0b0d11; color:#e5e7eb; }}
    .card {{ width:min(420px, calc(100vw - 32px)); background:#12151c; border:1px solid #1e2230; border-radius:18px; padding:28px; box-shadow:0 24px 80px rgba(0,0,0,.35); }}
    h1 {{ margin:0 0 6px; font-size:24px; }}
    p {{ margin:0 0 22px; color:#9ca3af; font-size:14px; }}
    label {{ display:block; font-size:12px; font-weight:700; color:#9ca3af; text-transform:uppercase; letter-spacing:.06em; margin:14px 0 6px; }}
    input {{ width:100%; background:#0b0d11; color:#fff; border:1px solid #263044; border-radius:10px; padding:12px 14px; font-size:15px; outline:none; }}
    input:focus {{ border-color:#3b82f6; box-shadow:0 0 0 3px rgba(59,130,246,.18); }}
    button {{ width:100%; margin-top:20px; border:0; border-radius:10px; padding:12px 14px; background:#3b82f6; color:white; font-weight:800; cursor:pointer; }}
    button:hover {{ filter:brightness(1.08); }}
    .error {{ background:rgba(239,68,68,.12); border:1px solid rgba(239,68,68,.35); color:#fecaca; padding:10px 12px; border-radius:10px; font-size:13px; margin-bottom:14px; }}
    .brand {{ display:flex; align-items:center; gap:10px; margin-bottom:20px; color:#60a5fa; font-weight:900; }}
    .dot {{ width:12px; height:12px; border-radius:50%; background:#3b82f6; box-shadow:0 0 24px #3b82f6; }}
  </style>
</head>
<body>
  <form class="card" method="post" action="/login">
    <div class="brand"><span class="dot"></span><span>Meta Tool</span></div>
    <h1>Iniciar sesión</h1>
    <p>Ingresa con tu usuario y contraseña.</p>
    {error_html}
    <label for="username">Usuario</label>
    <input id="username" name="username" autocomplete="username" required autofocus />
    <label for="password">Contraseña</label>
    <input id="password" name="password" type="password" autocomplete="current-password" required />
    <button type="submit">Entrar</button>
  </form>
</body>
</html>"""
    )
