from fastapi import APIRouter, HTTPException

from app.services.job_manager import cancel_job, delete_job, get_job, get_job_logs, list_jobs, rerun_job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def jobs_list():
    return list_jobs()


@router.get("/{job_id}")
def jobs_get(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/logs")
def jobs_logs(job_id: str, limit: int = 5000):
    if limit < 1:
        limit = 1
    if limit > 20000:
        limit = 20000
    return get_job_logs(job_id, limit=limit)


@router.post("/{job_id}/cancel")
def jobs_cancel(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return cancel_job(job_id)


@router.delete("/{job_id}")
def jobs_delete(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return delete_job(job_id)


@router.post("/{job_id}/rerun")
def jobs_rerun(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        return rerun_job(job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
