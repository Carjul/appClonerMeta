from fastapi import APIRouter, HTTPException

from app.db import configs_col
from app.schemas import BulkCloneRequest, DeleteCampaignsRequest, ExplorerRunRequest, SingleCloneRequest
from app.services.job_manager import create_job, get_job
from app.services.meta_runner import bulk_clone_command, delete_campaigns_command, explorer_command, single_clone_command
from app.utils import oid

router = APIRouter(prefix="/api", tags=["meta"])


def _get_config(config_id: str) -> dict:
    cfg = configs_col.find_one({"_id": oid(config_id)})
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    return cfg


@router.post("/explorer/run")
def run_explorer(payload: ExplorerRunRequest):
    cfg = _get_config(payload.configId)
    cmd, artifacts = explorer_command(cfg["bm_id"], cfg["access_token"])
    return create_job(
        job_type="explorer",
        config_id=payload.configId,
        payload={"bmId": cfg["bm_id"]},
        cmd=cmd,
        artifacts=artifacts,
    )


@router.get("/explorer/{job_id}/result")
def explorer_result(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "status": job.get("status"),
        "result": job.get("result"),
        "error": job.get("error"),
    }


@router.get("/explorer/cache/{config_id}")
def explorer_cache(config_id: str):
    cfg = _get_config(config_id)
    return {
        "configId": config_id,
        "cachedAt": cfg.get("explorer_cached_at"),
        "accounts": cfg.get("explorer_accounts", []),
    }


@router.post("/clone/bulk")
def run_bulk_clone(payload: BulkCloneRequest):
    cfg = _get_config(payload.configId)
    cmd, artifacts = bulk_clone_command(payload.campaignId, cfg["access_token"])
    return create_job(
        job_type="bulk_clone",
        config_id=payload.configId,
        payload={"campaignId": payload.campaignId},
        cmd=cmd,
        artifacts=artifacts,
    )


@router.post("/clone/single")
def run_single_clone(payload: SingleCloneRequest):
    if not payload.campaignIds:
        raise HTTPException(status_code=400, detail="campaignIds is required")
    cfg = _get_config(payload.configId)
    cmd, artifacts = single_clone_command(payload.campaignIds, cfg["access_token"])
    return create_job(
        job_type="single_clone",
        config_id=payload.configId,
        payload={"campaignIds": payload.campaignIds},
        cmd=cmd,
        artifacts=artifacts,
    )


@router.post("/delete/campaigns")
def run_delete_campaigns(payload: DeleteCampaignsRequest):
    if not payload.campaignIds:
        raise HTTPException(status_code=400, detail="campaignIds is required")
    cfg = _get_config(payload.configId)
    cmd, artifacts = delete_campaigns_command(payload.campaignIds, cfg["access_token"], payload.batch or 10)
    return create_job(
        job_type="delete_campaigns",
        config_id=payload.configId,
        payload={"campaignIds": payload.campaignIds, "batch": payload.batch or 10},
        cmd=cmd,
        artifacts=artifacts,
    )
