from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    SCHEDULER_ENABLED,
    SCHEDULER_HOUR,
    SCHEDULER_MAX_CONFIGS,
    SCHEDULER_MINUTE,
    SCHEDULER_TZ,
)
from app.routes.configs import router as configs_router
from app.routes.jobs import router as jobs_router
from app.routes.meta import router as meta_router
from app.services.scheduler import start_scheduler, stop_scheduler

app = FastAPI(title="Meta Automation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup_scheduler() -> None:
    start_scheduler()


@app.on_event("shutdown")
def _shutdown_scheduler() -> None:
    stop_scheduler()


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "scheduler": {
            "enabled": SCHEDULER_ENABLED,
            "timezone": SCHEDULER_TZ,
            "dailyHour": SCHEDULER_HOUR,
            "dailyMinute": SCHEDULER_MINUTE,
            "maxConfigs": SCHEDULER_MAX_CONFIGS,
        },
    }


app.include_router(configs_router)
app.include_router(jobs_router)
app.include_router(meta_router)


STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    def serve_index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    def serve_spa(path: str):
        if path.startswith("api"):
            raise HTTPException(status_code=404, detail="Not found")
        file_path = STATIC_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
