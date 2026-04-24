import threading
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import (
    SCHEDULER_CONFIG_IDS,
    SCHEDULER_CONFIG_NAMES,
    SCHEDULER_ENABLED,
    SCHEDULER_HOUR,
    SCHEDULER_MAX_CONFIGS,
    SCHEDULER_MINUTE,
    SCHEDULER_POLL_SECONDS,
    SCHEDULER_TZ,
)
from app.db import configs_col
from app.services.job_manager import create_job
from app.services.meta_runner import explorer_command
from app.utils import now_iso, oid

_thread = None
_stop_event = threading.Event()
_last_run_key = None
_lock = threading.Lock()


def _resolve_configs() -> list[dict]:
    if SCHEDULER_CONFIG_IDS:
        rows = []
        for cid in SCHEDULER_CONFIG_IDS:
            try:
                doc = configs_col.find_one({"_id": oid(cid)})
            except Exception:
                doc = None
            if doc:
                rows.append(doc)
        return rows[: max(1, SCHEDULER_MAX_CONFIGS)]

    if SCHEDULER_CONFIG_NAMES:
        rows = list(configs_col.find({"name": {"$in": SCHEDULER_CONFIG_NAMES}}))
        name_rank = {name: i for i, name in enumerate(SCHEDULER_CONFIG_NAMES)}
        rows.sort(key=lambda d: name_rank.get(d.get("name", ""), 999))
        return rows[: max(1, SCHEDULER_MAX_CONFIGS)]

    rows = list(configs_col.find().sort("created_at", 1).limit(max(1, SCHEDULER_MAX_CONFIGS)))
    return rows


def _run_explorer_for_configs() -> None:
    configs = _resolve_configs()
    if not configs:
        return

    for cfg in configs:
        token = cfg.get("access_token")
        bm_id = cfg.get("bm_id")
        config_id = str(cfg.get("_id"))
        if not token or not bm_id or not config_id:
            continue
        cmd, artifacts = explorer_command(bm_id, token)
        create_job(
            job_type="explorer",
            config_id=config_id,
            payload={"bmId": bm_id, "scheduled": True, "schedulerTz": SCHEDULER_TZ, "scheduledAt": now_iso()},
            cmd=cmd,
            artifacts=artifacts,
        )


def _should_run_now(now_local: datetime) -> bool:
    return now_local.hour == SCHEDULER_HOUR and now_local.minute == SCHEDULER_MINUTE


def _loop() -> None:
    global _last_run_key
    try:
        tz = ZoneInfo(SCHEDULER_TZ)
    except Exception:
        # Fallback for environments without tz database (e.g., some Windows setups).
        # Bogota is fixed UTC-5 (no DST).
        tz = timezone(timedelta(hours=-5), name="America/Bogota")

    while not _stop_event.is_set():
        now_local = datetime.now(tz)
        run_key = now_local.strftime("%Y-%m-%d")

        if _should_run_now(now_local):
            with _lock:
                if _last_run_key != run_key:
                    _last_run_key = run_key
                    _run_explorer_for_configs()

        _stop_event.wait(timeout=max(5, SCHEDULER_POLL_SECONDS))


def start_scheduler() -> None:
    global _thread
    if not SCHEDULER_ENABLED:
        return
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, daemon=True, name="daily-explorer-scheduler")
    _thread.start()


def stop_scheduler() -> None:
    _stop_event.set()
