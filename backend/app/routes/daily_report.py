from fastapi import APIRouter, HTTPException, Query

from app.db import configs_col, daily_reports_col
from app.schemas import DailyReportRunRequest
from app.services.daily_report_service import build_daily_report_snapshot
from app.utils import oid, serialize_doc


router = APIRouter(prefix="/api/daily-report", tags=["daily-report"])


def _get_config(config_id: str) -> dict:
    cfg = configs_col.find_one({"_id": oid(config_id)})
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    return cfg


@router.post("/run")
def run_daily_report(payload: DailyReportRunRequest):
    cfg = _get_config(payload.configId)
    token = cfg.get("access_token")
    bm_id = cfg.get("bm_id")
    if not token or not bm_id:
        raise HTTPException(status_code=400, detail="Config missing token or bmId")

    try:
        snapshot = build_daily_report_snapshot(
            config_id=payload.configId,
            bm_id=bm_id,
            token=token,
            periods=payload.periods,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Daily report fetch failed: {exc}")

    res = daily_reports_col.insert_one(snapshot)
    configs_col.update_one(
        {"_id": oid(payload.configId)},
        {"$set": {"daily_report_cached_at": snapshot.get("generated_at")}},
    )
    snapshot_out = dict(snapshot)
    snapshot_out["_id"] = str(res.inserted_id)
    return {"ok": True, "report": snapshot_out}


@router.get("/latest/{config_id}")
def latest_daily_report(config_id: str):
    _get_config(config_id)
    doc = daily_reports_col.find_one({"config_id": config_id}, sort=[("generated_at", -1)])
    if not doc:
        return {"configId": config_id, "report": None}
    return {"configId": config_id, "report": serialize_doc(doc)}


@router.get("/history/{config_id}")
def daily_report_history(config_id: str, limit: int = Query(default=20, ge=1, le=200)):
    _get_config(config_id)
    docs = daily_reports_col.find({"config_id": config_id}).sort("generated_at", -1).limit(limit)
    return {"configId": config_id, "reports": [serialize_doc(d) for d in docs]}
