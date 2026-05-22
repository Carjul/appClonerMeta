import threading

from app_b.config import FB_CATALOG_TRICK_RUNNER_ENABLED, FB_CATALOG_TRICK_RUNNER_INTERVAL_SECONDS
from app_b.routes.fb_catalog import trick_run_now
from app_b.utils import now_iso

_thread = None
_stop_event = threading.Event()
_lock = threading.Lock()
_last_started_at = None
_last_finished_at = None
_last_result = None
_last_error = ""


def _run_once() -> None:
    global _last_started_at, _last_finished_at, _last_result, _last_error
    with _lock:
        _last_started_at = now_iso()
        _last_error = ""
    try:
        result = trick_run_now()
        with _lock:
            _last_result = result
            _last_finished_at = now_iso()
    except Exception as exc:
        with _lock:
            _last_error = str(getattr(exc, "detail", None) or exc)
            _last_finished_at = now_iso()


def _loop() -> None:
    interval = max(60, FB_CATALOG_TRICK_RUNNER_INTERVAL_SECONDS)
    while not _stop_event.wait(interval):
        _run_once()


def start_fb_catalog_trick_runner() -> None:
    global _thread
    if not FB_CATALOG_TRICK_RUNNER_ENABLED:
        return
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, daemon=True, name="fb-catalog-trick-runner")
    _thread.start()


def stop_fb_catalog_trick_runner() -> None:
    _stop_event.set()


def fb_catalog_trick_runner_state() -> dict:
    with _lock:
        return {
            "enabled": FB_CATALOG_TRICK_RUNNER_ENABLED,
            "intervalSeconds": max(60, FB_CATALOG_TRICK_RUNNER_INTERVAL_SECONDS),
            "lastStartedAt": _last_started_at,
            "lastFinishedAt": _last_finished_at,
            "lastResult": _last_result,
            "lastError": _last_error,
        }
