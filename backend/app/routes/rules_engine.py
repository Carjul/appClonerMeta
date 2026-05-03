import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.db import configs_col, rules_col, rules_logs_col
from app.schemas import (
    RulesBulkDeleteRequest,
    RulesBulkToggleRequest,
    RulesCreateRequest,
    RulesToggleRequest,
)
from app.services.rules_engine_service import (
    build_log,
    create_meta_rule,
    delete_meta_rule,
    get_accounts_for_bm,
    get_campaigns,
    toggle_meta_rule,
)
from app.utils import now_iso, oid, serialize_doc

router = APIRouter(prefix="/api/rules", tags=["rules"])

PRESETS = [
    {
        "id": "pause_11pm",
        "name": "Pause at 11:00 PM",
        "name_es": "Pausar a las 11:00 PM",
        "desc": "Stop overnight spend",
        "desc_es": "Detener gasto nocturno",
        "help": "Pauses all selected campaigns at 11PM every night to prevent spending while you sleep.",
        "help_es": "Pausa todas las campanas a las 11PM cada noche para evitar gastar mientras duermes.",
        "type": "schedule",
        "action": "PAUSE",
        "hour": 23,
        "min": 0,
        "icon": "moon",
    },
    {
        "id": "activate_12pm",
        "name": "Activate at 12:00 PM",
        "name_es": "Activar a las 12:00 PM",
        "desc": "Resume spending at noon",
        "desc_es": "Reanudar gasto al mediodia",
        "help": "Turns on all selected campaigns at noon every day.",
        "help_es": "Activa todas las campanas al mediodia cada dia.",
        "type": "schedule",
        "action": "ACTIVATE",
        "hour": 12,
        "min": 0,
        "icon": "sun",
    },
    {
        "id": "pause_6am",
        "name": "Pause at 6:00 AM",
        "name_es": "Pausar a las 6:00 AM",
        "desc": "Stop early morning spend",
        "desc_es": "Detener gasto de madrugada",
        "help": "Pauses campaigns at 6AM.",
        "help_es": "Pausa campanas a las 6AM.",
        "type": "schedule",
        "action": "PAUSE",
        "hour": 6,
        "min": 0,
        "icon": "sunrise",
    },
    {
        "id": "activate_8am",
        "name": "Activate at 8:00 AM",
        "name_es": "Activar a las 8:00 AM",
        "desc": "Start the day",
        "desc_es": "Iniciar el dia",
        "help": "Activates campaigns at 8AM.",
        "help_es": "Activa campanas a las 8AM.",
        "type": "schedule",
        "action": "ACTIVATE",
        "hour": 8,
        "min": 0,
        "icon": "play",
    },
    {
        "id": "kill_cpa_co",
        "name": "Kill CPA CO > $20",
        "name_es": "Matar CPA CO > $20",
        "desc": "Pause if checkout CPA too high",
        "desc_es": "Pausar si CPA checkout muy alto",
        "help": "If CPA Checkout > $20 AND Spend > $50, pause the adset.",
        "help_es": "Si CPA Checkout > $20 Y Gasto > $50, pausar el adset.",
        "type": "condition",
        "action": "PAUSE",
        "time_range": "last_3d",
        "check_freq": "30min",
        "conditions": [{"metric": "cpa_checkout", "op": ">", "val": 20}, {"metric": "spend", "op": ">", "val": 50}],
        "icon": "x-circle",
    },
    {
        "id": "kill_cpc_150",
        "name": "Kill CPC > $1.50",
        "name_es": "Matar CPC > $1.50",
        "desc": "Pause if CPC exceeds $1.50",
        "desc_es": "Pausar si CPC supera $1.50",
        "help": "If CPC > $1.50 AND Spend > $10, pause the adset (video ads).",
        "help_es": "Si CPC > $1.50 Y Gasto > $10, pausar el adset (anuncios de video).",
        "type": "condition",
        "action": "PAUSE",
        "time_range": "last_3d",
        "check_freq": "30min",
        "conditions": [{"metric": "cpc", "op": ">", "val": 1.5}, {"metric": "spend", "op": ">", "val": 10}],
        "icon": "trending-down",
    },
    {
        "id": "kill_cpc_100",
        "name": "Kill CPC > $1.00",
        "name_es": "Matar CPC > $1.00",
        "desc": "Pause if CPC exceeds $1.00",
        "desc_es": "Pausar si CPC supera $1.00",
        "help": "If CPC > $1.00 AND Spend > $10, pause the adset (image ads).",
        "help_es": "Si CPC > $1.00 Y Gasto > $10, pausar el adset (anuncios de imagen).",
        "type": "condition",
        "action": "PAUSE",
        "time_range": "last_3d",
        "check_freq": "30min",
        "conditions": [{"metric": "cpc", "op": ">", "val": 1.0}, {"metric": "spend", "op": ">", "val": 10}],
        "icon": "trending-down",
    },
    {
        "id": "pause_no_spend",
        "name": "Pause $0 Spend (3d)",
        "name_es": "Pausar $0 Gasto (3d)",
        "desc": "Pause if no spend for 3 days",
        "desc_es": "Pausar si no gasta en 3 dias",
        "help": "If Spend < $0.01 over last 3 days AND Days Running >= 3, pause.",
        "help_es": "Si Gasto < $0.01 en 3 dias Y Dias corriendo >= 3, pausar.",
        "type": "condition",
        "action": "PAUSE",
        "time_range": "last_3d",
        "check_freq": "30min",
        "conditions": [{"metric": "spend", "op": "<", "val": 0.01}, {"metric": "days_running", "op": ">=", "val": 3}],
        "icon": "alert",
    },
    {
        "id": "no_purchase_3d",
        "name": "No Purchase 3 Days",
        "name_es": "Sin Venta 3 Dias",
        "desc": "Pause if 0 purchases after 3 days",
        "desc_es": "Pausar si 0 ventas en 3 dias",
        "help": "If Purchases < 1 AND Days Running >= 3 AND Spend > $5, pause.",
        "help_es": "Si Compras < 1 Y Dias corriendo >= 3 Y Gasto > $5, pausar.",
        "type": "condition",
        "action": "PAUSE",
        "time_range": "last_3d",
        "check_freq": "30min",
        "conditions": [
            {"metric": "purchases", "op": "<", "val": 1},
            {"metric": "days_running", "op": ">=", "val": 3},
            {"metric": "spend", "op": ">", "val": 5},
        ],
        "icon": "slash",
    },
    {
        "id": "budget_bump",
        "name": "Budget $1 -> $1.05",
        "name_es": "Presupuesto $1 -> $1.05",
        "desc": "Bump budget if not spending",
        "desc_es": "Subir presupuesto si no gasta",
        "help": "If Spend = $0 AND Days Running >= 1, indicates adset is stuck. Requires manual budget bump.",
        "help_es": "Si Gasto = $0 Y Dias corriendo >= 1, indica que el adset esta trabado. Requiere bump manual.",
        "type": "condition",
        "action": "PAUSE",
        "time_range": "last_3d",
        "check_freq": "30min",
        "conditions": [{"metric": "spend", "op": "<", "val": 0.01}, {"metric": "days_running", "op": ">=", "val": 1}],
        "icon": "dollar",
    },
]


def _get_config(config_id: str) -> dict:
    cfg = configs_col.find_one({"_id": oid(config_id)})
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    if not cfg.get("access_token") or not cfg.get("bm_id"):
        raise HTTPException(status_code=400, detail="Config missing token or bmId")
    return cfg


def _insert_log(config_id: str, rule_name: str, action: str, ok: bool, detail: str, account_name: str) -> None:
    rules_logs_col.insert_one(build_log(config_id, rule_name, action, ok, detail, account_name))


@router.get("/presets")
def list_presets():
    return PRESETS


@router.get("/config/{config_id}/accounts")
def list_accounts(config_id: str):
    cfg = _get_config(config_id)
    try:
        rows = get_accounts_for_bm(cfg["bm_id"], cfg["access_token"])
        return {"configId": config_id, "accounts": rows}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Accounts fetch failed: {exc}")


@router.get("/config/{config_id}/accounts/{account_id}/campaigns")
def list_campaigns(config_id: str, account_id: str):
    cfg = _get_config(config_id)
    try:
        active = get_campaigns(account_id, cfg["access_token"], "ACTIVE")
        paused = get_campaigns(account_id, cfg["access_token"], "PAUSED")
        merged = active + [c for c in paused if c.get("id") not in {a.get("id") for a in active}]
        return {"configId": config_id, "accountId": account_id, "campaigns": merged}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Campaigns fetch failed: {exc}")


@router.get("/config/{config_id}")
def list_rules(config_id: str):
    _get_config(config_id)
    docs = rules_col.find({"config_id": config_id}).sort("created_at", -1)
    return {"configId": config_id, "rules": [serialize_doc(d) for d in docs]}


@router.get("/config/{config_id}/logs")
def list_logs(config_id: str, limit: int = Query(default=80, ge=1, le=500)):
    _get_config(config_id)
    docs = rules_logs_col.find({"config_id": config_id}).sort("timestamp", -1).limit(limit)
    return {"configId": config_id, "logs": [serialize_doc(d) for d in docs]}


@router.post("/config/{config_id}/logs/clear")
def clear_logs(config_id: str):
    _get_config(config_id)
    rules_logs_col.delete_many({"config_id": config_id})
    return {"ok": True}


@router.post("/config/{config_id}")
def create_rule(config_id: str, payload: RulesCreateRequest):
    cfg = _get_config(config_id)
    if not payload.campaignIds:
        raise HTTPException(status_code=400, detail="campaignIds is required")

    campaign_names = {}
    try:
        for c in get_campaigns(payload.accountId, cfg["access_token"], "ACTIVE") + get_campaigns(payload.accountId, cfg["access_token"], "PAUSED"):
            if c.get("id") in payload.campaignIds:
                campaign_names[c["id"]] = c.get("name", c["id"])
    except Exception:
        campaign_names = {}

    if payload.source == "preset":
        preset = next((x for x in PRESETS if x["id"] == payload.presetId), None)
        if not preset:
            raise HTTPException(status_code=400, detail="Invalid presetId")
        rule = {
            "id": f"{preset['id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "name": (payload.customName or "").strip() or f"{preset['name']} -- {payload.accountName}",
            "type": preset["type"],
            "action": preset["action"],
            "campaign_ids": payload.campaignIds,
            "campaign_names": campaign_names,
            "account_id": payload.accountId,
            "account_name": payload.accountName,
            "enabled": True,
            "is_custom": False,
            "created_at": now_iso(),
            "config_id": config_id,
        }
        if preset["type"] == "schedule":
            rule["hour"] = preset["hour"]
            rule["min"] = preset["min"]
        else:
            rule["conditions"] = preset.get("conditions", [])
            rule["time_range"] = preset.get("time_range", "last_3d")
            rule["check_freq"] = preset.get("check_freq", "30min")
    else:
        custom_type = payload.customType or "schedule"
        rule = {
            "id": f"custom_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "name": (payload.customName or "").strip() or f"Custom -- {payload.accountName}",
            "type": custom_type,
            "campaign_ids": payload.campaignIds,
            "campaign_names": campaign_names,
            "account_id": payload.accountId,
            "account_name": payload.accountName,
            "enabled": True,
            "is_custom": True,
            "created_at": now_iso(),
            "config_id": config_id,
        }
        if custom_type == "schedule":
            rule["action"] = payload.customAction or "PAUSE"
            rule["hour"] = int(payload.customHour if payload.customHour is not None else 23)
            rule["min"] = int(payload.customMinute if payload.customMinute is not None else 0)
        else:
            rule["action"] = payload.customActionCondition or "PAUSE"
            rule["time_range"] = payload.timeRange or "last_3d"
            rule["check_freq"] = payload.checkFreq or "30min"
            rule["conditions"] = [c.model_dump() for c in (payload.conditions or [])]

    try:
        result = create_meta_rule(payload.accountId, cfg["access_token"], rule)
    except Exception as exc:
        _insert_log(config_id, rule["name"], "CREATE FAILED", False, str(exc), payload.accountName)
        raise HTTPException(status_code=502, detail=f"Meta create rule failed: {exc}")

    if "id" in result:
        rule["meta_rule_id"] = result["id"]
        _insert_log(config_id, rule["name"], "CREATED ON META", True, "OK", payload.accountName)
    else:
        detail = json.dumps(result)
        _insert_log(config_id, rule["name"], "CREATE FAILED", False, detail, payload.accountName)

    insert = rules_col.insert_one(rule)
    doc = rules_col.find_one({"_id": insert.inserted_id})
    if not doc:
        raise HTTPException(status_code=500, detail="Rule saved but not found")
    return {"ok": True, "rule": serialize_doc(dict(doc))}


@router.post("/{rule_id}/toggle")
def toggle_rule(rule_id: str, payload: RulesToggleRequest):
    doc = rules_col.find_one({"_id": oid(rule_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Rule not found")
    cfg = _get_config(doc["config_id"])
    enabled = bool(payload.enabled)

    if doc.get("meta_rule_id"):
        try:
            toggle_meta_rule(doc["meta_rule_id"], cfg["access_token"], enabled)
            _insert_log(doc["config_id"], doc.get("name", "Rule"), "ENABLED" if enabled else "PAUSED", True, "Status updated on Meta", doc.get("account_name", ""))
        except Exception as exc:
            _insert_log(doc["config_id"], doc.get("name", "Rule"), "TOGGLE FAILED", False, str(exc), doc.get("account_name", ""))
            raise HTTPException(status_code=502, detail=f"Meta toggle failed: {exc}")

    rules_col.update_one({"_id": oid(rule_id)}, {"$set": {"enabled": enabled, "updated_at": now_iso()}})
    updated = rules_col.find_one({"_id": oid(rule_id)})
    if not updated:
        raise HTTPException(status_code=500, detail="Rule updated but not found")
    return {"ok": True, "rule": serialize_doc(dict(updated))}


@router.delete("/{rule_id}")
def delete_rule(rule_id: str):
    doc = rules_col.find_one({"_id": oid(rule_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Rule not found")
    cfg = _get_config(doc["config_id"])

    if doc.get("meta_rule_id"):
        try:
            delete_meta_rule(doc["meta_rule_id"], cfg["access_token"])
            _insert_log(doc["config_id"], doc.get("name", "Rule"), "DELETED FROM META", True, "Rule removed", doc.get("account_name", ""))
        except Exception as exc:
            _insert_log(doc["config_id"], doc.get("name", "Rule"), "DELETE FAILED", False, str(exc), doc.get("account_name", ""))
            raise HTTPException(status_code=502, detail=f"Meta delete failed: {exc}")

    rules_col.delete_one({"_id": oid(rule_id)})
    return {"ok": True}


@router.post("/config/{config_id}/bulk/toggle")
def bulk_toggle(config_id: str, payload: RulesBulkToggleRequest):
    cfg = _get_config(config_id)
    if not payload.ruleIds:
        raise HTTPException(status_code=400, detail="ruleIds is required")
    enable = payload.action == "activate"

    docs = list(rules_col.find({"_id": {"$in": [oid(rid) for rid in payload.ruleIds]}, "config_id": config_id}))
    for d in docs:
        if d.get("meta_rule_id"):
            try:
                toggle_meta_rule(d["meta_rule_id"], cfg["access_token"], enable)
            except Exception:
                pass
        rules_col.update_one({"_id": d["_id"]}, {"$set": {"enabled": enable, "updated_at": now_iso()}})
    return {"ok": True, "updated": len(docs)}


@router.post("/config/{config_id}/bulk/delete")
def bulk_delete(config_id: str, payload: RulesBulkDeleteRequest):
    cfg = _get_config(config_id)
    if not payload.ruleIds:
        raise HTTPException(status_code=400, detail="ruleIds is required")
    ids = [oid(rid) for rid in payload.ruleIds]
    docs = list(rules_col.find({"_id": {"$in": ids}, "config_id": config_id}))
    for d in docs:
        if d.get("meta_rule_id"):
            try:
                delete_meta_rule(d["meta_rule_id"], cfg["access_token"])
            except Exception:
                pass
    rules_col.delete_many({"_id": {"$in": ids}, "config_id": config_id})
    return {"ok": True, "deleted": len(docs)}
