import threading
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import (
    SCHEDULER_CONFIG_IDS,
    SCHEDULER_CONFIG_NAMES,
    SCHEDULER_ENABLED,
    SCHEDULER_HOUR,
    SCHEDULER_INTRADAY_ENABLED,
    SCHEDULER_INTRADAY_INTERVAL_MINUTES,
    SCHEDULER_INTRADAY_START_HOUR,
    SCHEDULER_INTRADAY_STOP_HOUR,
    SCHEDULER_MAX_CONFIGS,
    SCHEDULER_MINUTE,
    SCHEDULER_POLL_SECONDS,
    SCHEDULER_RUN_DAILY_REPORT,
    SCHEDULER_RUN_EXPLORER,
    SCHEDULER_TZ,
)
from app.db import configs_col, daily_reports_col
from app.services.job_manager import create_job
from app.services.daily_report_service import build_daily_report_snapshot
from app.services.meta_runner import explorer_command
from app.utils import now_iso, oid

_thread = None
_stop_event = threading.Event()
_last_run_key = None
_last_intraday_slot = None
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


def _run_for_configs() -> None:
    configs = _resolve_configs()
    if not configs:
        return

    for cfg in configs:
        token = cfg.get("access_token")
        bm_id = cfg.get("bm_id")
        config_id = str(cfg.get("_id"))
        if not token or not bm_id or not config_id:
            continue
        if SCHEDULER_RUN_EXPLORER:
            cmd, artifacts = explorer_command(bm_id, token)
            create_job(
                job_type="explorer",
                config_id=config_id,
                payload={"bmId": bm_id, "scheduled": True, "schedulerTz": SCHEDULER_TZ, "scheduledAt": now_iso()},
                cmd=cmd,
                artifacts=artifacts,
            )

        if SCHEDULER_RUN_DAILY_REPORT:
            try:
                snapshot = build_daily_report_snapshot(
                    config_id=config_id,
                    bm_id=bm_id,
                    token=token,
                    periods=["today", "yesterday", "lifetime"],
                )
                daily_reports_col.insert_one(snapshot)
                configs_col.update_one(
                    {"_id": oid(config_id)},
                    {"$set": {"daily_report_cached_at": snapshot.get("generated_at")}},
                )
            except Exception:
                continue


def _should_run_now(now_local: datetime) -> bool:
    return now_local.hour == SCHEDULER_HOUR and now_local.minute == SCHEDULER_MINUTE


def _intraday_slot(now_local: datetime) -> int | None:
    if not SCHEDULER_INTRADAY_ENABLED:
        return None
    if SCHEDULER_INTRADAY_INTERVAL_MINUTES <= 0:
        return None
    if now_local.hour < SCHEDULER_INTRADAY_START_HOUR or now_local.hour >= SCHEDULER_INTRADAY_STOP_HOUR:
        return None

    start_total = SCHEDULER_INTRADAY_START_HOUR * 60
    now_total = now_local.hour * 60 + now_local.minute
    elapsed = now_total - start_total
    if elapsed < 0:
        return None
    if elapsed % SCHEDULER_INTRADAY_INTERVAL_MINUTES != 0:
        return None
    return elapsed // SCHEDULER_INTRADAY_INTERVAL_MINUTES


def _loop() -> None:
    global _last_run_key, _last_intraday_slot
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
                    _run_for_configs()

        slot = _intraday_slot(now_local)
        if slot is not None:
            slot_key = f"{run_key}:{slot}"
            with _lock:
                if _last_intraday_slot != slot_key:
                    _last_intraday_slot = slot_key
                    _run_for_configs()

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


def scheduler_state() -> dict:
    return {
        "lastDailyRunKey": _last_run_key,
        "lastIntradaySlot": _last_intraday_slot,
    }
