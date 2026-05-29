from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from pymongo import MongoClient

from backend.auth import current_user, is_admin
from backend.core.config import settings

router = APIRouter(prefix="/api/users", tags=["users"])

_client = MongoClient(settings.MONGO_URI)
_db = _client[settings.DB_NAME]
_users = _db["Users"]


class UserUpdate(BaseModel):
    role: str | None = None
    status: str | None = None


def _require_admin(request: Request):
    user = current_user(request)
    if not user or not is_admin(user):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc.get("_id")),
        "name": doc.get("Name") or doc.get("name") or "",
        "email": doc.get("Email") or doc.get("email") or "",
        "role": doc.get("Rol") or doc.get("role") or "Cliente",
        "status": doc.get("Status") or doc.get("status") or "active",
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at")),
        "email_verified_at": _iso(doc.get("email_verified_at")),
    }


def _iso(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value or None


@router.get("")
def list_users(request: Request):
    _require_admin(request)
    rows = _users.find({}, {
        "Password": 0,
        "PasswordHash": 0,
        "activation_token_hash": 0,
        "activation_expires_at": 0,
        "reset_token_hash": 0,
        "reset_expires_at": 0,
    }).sort("created_at", -1)
    return [_serialize(row) for row in rows]


@router.patch("/{user_id}")
def update_user(user_id: str, payload: UserUpdate, request: Request):
    _require_admin(request)
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")

    updates = {}
    if payload.role is not None:
        role = payload.role.strip()
        if role not in {"Admin", "SuperAdmin", "Cliente"}:
            raise HTTPException(status_code=400, detail="Invalid role")
        updates["Rol"] = role
    if payload.status is not None:
        status = payload.status.strip().lower()
        if status not in {"active", "inactive"}:
            raise HTTPException(status_code=400, detail="Invalid status")
        updates["Status"] = status
    if not updates:
        raise HTTPException(status_code=400, detail="No changes")
    updates["updated_at"] = datetime.utcnow()

    result = _users.update_one({"_id": oid}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    doc = _users.find_one({"_id": oid})
    return _serialize(doc)
