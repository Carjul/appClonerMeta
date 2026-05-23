from fastapi import APIRouter, HTTPException
import requests

from backend.api.db import configs_col
from backend.api.schemas import ConfigCreate, ConfigUpdate
from backend.api.utils import now_iso, oid, serialize_doc

router = APIRouter(prefix="/api/configs", tags=["configs"])


def _public_config(doc: dict) -> dict:
    out = serialize_doc(doc)
    token = out.pop("access_token", "") or ""
    out["tokenConfigured"] = bool(token)
    return out


@router.get("")
def list_configs():
    docs = configs_col.find().sort("created_at", -1)
    return [_public_config(d) for d in docs]


@router.get("/{config_id}")
def get_config(config_id: str):
    doc = configs_col.find_one({"_id": oid(config_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Config not found")
    return _public_config(doc)


@router.post("")
def create_config(payload: ConfigCreate):
    if configs_col.find_one({"name": payload.name}):
        raise HTTPException(status_code=409, detail="Config name already exists")
    doc = {
        "name": payload.name,
        "bm_id": payload.bmId,
        "access_token": payload.accessToken,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    res = configs_col.insert_one(doc)
    created = configs_col.find_one({"_id": res.inserted_id})
    return _public_config(created)


@router.put("/{config_id}")
def update_config(config_id: str, payload: ConfigUpdate):
    updates = {}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.bmId is not None:
        updates["bm_id"] = payload.bmId
    if payload.accessToken is not None:
        token = payload.accessToken.strip()
        if token:
            updates["access_token"] = token
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["updated_at"] = now_iso()
    res = configs_col.update_one({"_id": oid(config_id)}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Config not found")
    doc = configs_col.find_one({"_id": oid(config_id)})
    return _public_config(doc)


@router.delete("/{config_id}")
def delete_config(config_id: str):
    res = configs_col.delete_one({"_id": oid(config_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Config not found")
    return {"ok": True}


@router.post("/{config_id}/test")
def test_config(config_id: str):
    doc = configs_col.find_one({"_id": oid(config_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Config not found")
    token = (doc.get("access_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Config token not found")
    res = requests.get("https://graph.facebook.com/v21.0/me", params={"fields": "id,name", "access_token": token}, timeout=30)
    try:
        payload = res.json()
    except ValueError:
        payload = {"error": {"message": res.text[:300]}}
    ok = res.status_code < 400 and not payload.get("error")
    updates = {"is_valid": ok, "last_tested_at": now_iso(), "last_error": "" if ok else payload.get("error", {}).get("message", str(payload)), "updated_at": now_iso()}
    configs_col.update_one({"_id": oid(config_id)}, {"$set": updates})
    if not ok:
        raise HTTPException(status_code=400, detail=updates["last_error"])
    return {"ok": True, "me": payload}
