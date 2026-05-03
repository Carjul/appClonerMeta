from pathlib import Path
import threading
import time

import requests
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    SCHEDULER_ENABLED,
    SCHEDULER_HOUR,
    SCHEDULER_INTRADAY_ENABLED,
    SCHEDULER_INTRADAY_INTERVAL_MINUTES,
    SCHEDULER_INTRADAY_START_HOUR,
    SCHEDULER_INTRADAY_STOP_HOUR,
    SCHEDULER_MAX_CONFIGS,
    SCHEDULER_MINUTE,
    SCHEDULER_RUN_DAILY_REPORT,
    SCHEDULER_RUN_EXPLORER,
    SCHEDULER_TZ,
    APP_URL,
)
from app.routes.configs import router as configs_router
from app.routes.daily_report import router as daily_report_router
from app.routes.jobs import router as jobs_router
from app.routes.meta import router as meta_router
from app.routes.rules_engine import router as rules_engine_router
from app.services.scheduler import scheduler_state, start_scheduler, stop_scheduler

_HEALTH_PING_URL = f"{APP_URL}/api/health"
_HEALTH_PING_INTERVAL_SECONDS = 600
_health_ping_stop = threading.Event()
_health_ping_thread = None


def _health_ping_loop() -> None:
    while not _health_ping_stop.is_set():
        try:
            res = requests.get(_HEALTH_PING_URL, timeout=20)
            res.raise_for_status()
            print(f"[health-ping] {res.json()}", flush=True)
        except Exception as exc:
            print(f"[health-ping] ERROR: {exc}", flush=True)
        _health_ping_stop.wait(_HEALTH_PING_INTERVAL_SECONDS)


def _start_health_ping() -> None:
    global _health_ping_thread
    if _health_ping_thread and _health_ping_thread.is_alive():
        return
    _health_ping_stop.clear()
    _health_ping_thread = threading.Thread(target=_health_ping_loop, daemon=True, name="health-ping-loop")
    _health_ping_thread.start()


def _stop_health_ping() -> None:
    _health_ping_stop.set()

app = FastAPI(title="Meta API Tool", version="1.2.3")

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
    _start_health_ping()


@app.on_event("shutdown")
def _shutdown_scheduler() -> None:
    stop_scheduler()
    _stop_health_ping()


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
            "runExplorer": SCHEDULER_RUN_EXPLORER,
            "runDailyReport": SCHEDULER_RUN_DAILY_REPORT,
            "intraday": {
                "enabled": SCHEDULER_INTRADAY_ENABLED,
                "startHour": SCHEDULER_INTRADAY_START_HOUR,
                "stopHour": SCHEDULER_INTRADAY_STOP_HOUR,
                "intervalMinutes": SCHEDULER_INTRADAY_INTERVAL_MINUTES,
            },
            "state": scheduler_state(),
        },
    }


app.include_router(configs_router)
app.include_router(daily_report_router)
app.include_router(jobs_router)
app.include_router(meta_router)
app.include_router(rules_engine_router)


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
