from fastapi import APIRouter, HTTPException

from app.services.job_manager import cancel_job, delete_job, get_job, get_job_logs, list_jobs

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
def jobs_logs(job_id: str):
    return get_job_logs(job_id)


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
