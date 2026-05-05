import json
import os
import re
import subprocess
import threading
from typing import Any, Dict, List, Optional

from app.db import configs_col, job_logs_col, jobs_col
from app.services.meta_runner import (
    ROOT_DIR,
    bulk_clone_command,
    campaign_status_command,
    delete_campaigns_command,
    explorer_command,
    reduce_budgets_command,
    single_clone_command,
)
from app.utils import now_iso, oid, serialize_doc

_proc_lock = threading.Lock()
_processes: Dict[str, subprocess.Popen] = {}


def _to_abs_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(ROOT_DIR, path))


def _extract_file_path_from_line(line: str) -> Optional[str]:
    text = line.strip()
    if not text:
        return None

    patterns = [
        r"Resultado guardado en:\s*(.+)$",
        r"Resultados guardados en:\s*(.+)$",
        r"Report:\s*(.+)$",
        r"Log guardado en:\s*(.+)$",
        r"State\s*:\s*(.+)$",
        r"Log CSV\s*:\s*(.+)$",
        r"Log\s*:\s*(.+)$",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip().strip('"')
    return None


def _append_log(job_id: str, level: str, message: str) -> None:
    job_logs_col.insert_one(
        {
            "job_id": job_id,
            "timestamp": now_iso(),
            "level": level,
            "message": message.rstrip("\n"),
        }
    )


def _update_job(job_id: str, updates: Dict[str, Any]) -> None:
    jobs_col.update_one({"_id": oid(job_id)}, {"$set": updates})


def _progress_from_line(job_type: str, payload: Dict[str, Any], line: str, counters: Dict[str, int]) -> Optional[Dict[str, Any]]:
    text = line.strip()
    if not text:
        return None

    if job_type == "explorer":
        if "Total cuentas:" in text:
            try:
                count = int(text.split(":", 1)[1].strip())
                return {"percent": 90, "message": f"Cuentas encontradas: {count}"}
            except Exception:
                return None
        if "Total campañas:" in text or "Total campanas:" in text:
            try:
                count = int(text.split(":", 1)[1].strip())
                return {"percent": 100, "message": f"Campañas encontradas: {count}"}
            except Exception:
                return None
        return None

    if job_type == "single_clone":
        copies_to_create = int(payload.get("copiesToCreate", 49) or 49)
        total = max(1, len(payload.get("campaignIds", [])) * max(1, copies_to_create))
        if " ad OK " in f" {text} ":
            counters["ok"] = counters.get("ok", 0) + 1
        if " SKIP completo" in text:
            counters["ok"] = counters.get("ok", 0) + 1
        if "GUARD" in text or "ERR_" in text:
            counters["done"] = counters.get("done", 0) + 1
        done = max(counters.get("done", 0), counters.get("ok", 0))
        if counters.get("ok", 0) > counters.get("done", 0):
            counters["done"] = counters["ok"]
            done = counters["done"]
        percent = min(99, int(done * 100 / total))
        return {"percent": percent, "message": f"Progreso {done}/{total}"}

    if job_type == "bulk_clone":
        total = 200
        if "| OK" in text and "ad OK" in text:
            counters["done"] = counters.get("done", 0) + 1
        if "SKIP completo" in text:
            counters["done"] = counters.get("done", 0) + 1
        if "| GUARD" in text or "| ERROR" in text:
            counters["done"] = counters.get("done", 0) + 1
        done = counters.get("done", 0)
        percent = min(99, int(done * 100 / total))
        return {"percent": percent, "message": f"Progreso {done}/{total}"}

    if job_type == "delete_campaigns":
        total = max(1, len(payload.get("campaignIds", [])))
        if "| OK" in text and "Deleted campaign:" in text:
            counters["done"] = counters.get("done", 0) + 1
        if "| ERROR" in text and "Failed campaign" in text:
            counters["done"] = counters.get("done", 0) + 1
        done = counters.get("done", 0)
        percent = min(99, int(done * 100 / total))
        return {"percent": percent, "message": f"Eliminadas {done}/{total}"}

    if job_type == "campaign_status":
        total = max(1, len(payload.get("campaignIds", [])))
        if "[OK]" in text and "Campaña" in text and "actualizada" in text:
            counters["done"] = counters.get("done", 0) + 1
        if "[INFO]" in text and "ya tiene estatus" in text:
            counters["done"] = counters.get("done", 0) + 1
        if "[FAIL]" in text and "No se pudo validar" in text:
            counters["done"] = counters.get("done", 0) + 1
        if "[FAIL]" in text and "Error actualizando" in text:
            counters["done"] = counters.get("done", 0) + 1
        done = counters.get("done", 0)
        percent = min(99, int(done * 100 / total))
        return {"percent": percent, "message": f"Status {done}/{total}"}

    return None


def _run_job_thread(job_id: str, job_type: str, payload: Dict[str, Any], cmd: List[str], artifacts: Dict[str, str]) -> None:
    _update_job(job_id, {"status": "running", "started_at": now_iso()})
    _append_log(job_id, "INFO", f"Starting command: {' '.join(cmd)}")

    generated_paths = set()
    for value in (artifacts or {}).values():
        if isinstance(value, str) and value:
            generated_paths.add(_to_abs_path(value))

    proc = subprocess.Popen(
        cmd,
        cwd=ROOT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    with _proc_lock:
        _processes[job_id] = proc

    cancelled = False
    counters: Dict[str, int] = {"done": 0, "ok": 0}
    try:
        if proc.stdout:
            for line in proc.stdout:
                _append_log(job_id, "INFO", line)
                file_path = _extract_file_path_from_line(line)
                if file_path:
                    generated_paths.add(_to_abs_path(file_path))
                progress = _progress_from_line(job_type, payload, line, counters)
                if progress:
                    _update_job(job_id, {"progress": progress})
                job = jobs_col.find_one({"_id": oid(job_id)}, {"cancel_requested": 1})
                if job and job.get("cancel_requested"):
                    cancelled = True
                    proc.terminate()
                    _append_log(job_id, "WARN", "Cancel requested. Terminating process...")
                    break

        rc = proc.wait()
        result_payload: Optional[Dict[str, Any]] = None

        output_json = artifacts.get("output_json")
        if output_json and os.path.exists(output_json):
            try:
                with open(output_json, "r", encoding="utf-8") as f:
                    result_payload = {"accounts": json.load(f)}
            except Exception as exc:
                _append_log(job_id, "ERROR", f"Failed to parse output JSON: {exc}")

        if cancelled:
            _update_job(job_id, {"status": "cancelled", "finished_at": now_iso(), "return_code": rc, "progress": {"percent": min(99, counters.get("done", 0)), "message": "Cancelado"}})
        elif rc == 0:
            updates = {"status": "completed", "finished_at": now_iso(), "return_code": rc}
            updates["progress"] = {"percent": 100, "message": "Completado"}
            existing_files = [p for p in sorted(generated_paths) if os.path.isfile(p)]
            if existing_files:
                updates["output_files"] = existing_files
            if result_payload is not None:
                updates["result"] = result_payload
            _update_job(job_id, updates)

            job_doc = jobs_col.find_one({"_id": oid(job_id)}, {"config_id": 1})
            config_id = job_doc.get("config_id") if job_doc else None

            if job_type == "explorer" and result_payload is not None and config_id:
                configs_col.update_one(
                    {"_id": oid(config_id)},
                    {
                        "$set": {
                            "explorer_accounts": result_payload.get("accounts", []),
                            "explorer_cached_at": now_iso(),
                        }
                    },
                )

            if job_type == "delete_campaigns" and config_id:
                campaign_ids = set(payload.get("campaignIds", []))
                cfg = configs_col.find_one({"_id": oid(config_id)}, {"explorer_accounts": 1})
                accounts = (cfg or {}).get("explorer_accounts", [])
                if accounts and campaign_ids:
                    new_accounts = []
                    for acc in accounts:
                        acc_copy = dict(acc)
                        campaigns = acc_copy.get("campaigns", [])
                        acc_copy["campaigns"] = [c for c in campaigns if c.get("id") not in campaign_ids]
                        new_accounts.append(acc_copy)
                    configs_col.update_one(
                        {"_id": oid(config_id)},
                        {
                            "$set": {
                                "explorer_accounts": new_accounts,
                                "explorer_cached_at": now_iso(),
                            }
                        },
                    )

            if job_type == "campaign_status" and config_id:
                campaign_ids = set(payload.get("campaignIds", []))
                target_status = (payload.get("status") or "").upper()
                cfg = configs_col.find_one({"_id": oid(config_id)}, {"explorer_accounts": 1})
                accounts = (cfg or {}).get("explorer_accounts", [])
                if accounts and campaign_ids and target_status in ("ACTIVE", "PAUSED"):
                    new_accounts = []
                    for acc in accounts:
                        acc_copy = dict(acc)
                        campaigns = []
                        for c in acc_copy.get("campaigns", []):
                            c_copy = dict(c)
                            if c_copy.get("id") in campaign_ids:
                                c_copy["status"] = target_status
                            campaigns.append(c_copy)
                        acc_copy["campaigns"] = campaigns
                        new_accounts.append(acc_copy)
                    configs_col.update_one(
                        {"_id": oid(config_id)},
                        {
                            "$set": {
                                "explorer_accounts": new_accounts,
                                "explorer_cached_at": now_iso(),
                            }
                        },
                    )
        else:
            _update_job(
                job_id,
                {
                    "status": "failed",
                    "finished_at": now_iso(),
                    "return_code": rc,
                    "error": f"Process exited with code {rc}",
                },
            )
    except Exception as exc:
        _append_log(job_id, "ERROR", f"Job execution exception: {exc}")
        _update_job(job_id, {"status": "failed", "finished_at": now_iso(), "error": str(exc)})
    finally:
        with _proc_lock:
            _processes.pop(job_id, None)


def create_job(job_type: str, config_id: str, payload: Dict[str, Any], cmd: List[str], artifacts: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    doc = {
        "type": job_type,
        "config_id": config_id,
        "payload": payload,
        "status": "queued",
        "created_at": now_iso(),
        "cancel_requested": False,
        "artifacts": artifacts or {},
        "progress": {"percent": 0, "message": "En cola"},
    }
    res = jobs_col.insert_one(doc)
    job_id = str(res.inserted_id)

    thread = threading.Thread(target=_run_job_thread, args=(job_id, job_type, payload, cmd, artifacts or {}), daemon=True)
    thread.start()

    return {"jobId": job_id, "status": "queued"}


def list_jobs(limit: int = 100) -> List[Dict[str, Any]]:
    cur = jobs_col.find().sort("created_at", -1).limit(limit)
    return [serialize_doc(d) for d in cur]


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    return serialize_doc(jobs_col.find_one({"_id": oid(job_id)}))


def get_job_logs(job_id: str, limit: int = 5000) -> List[Dict[str, Any]]:
    cur = job_logs_col.find({"job_id": job_id}).sort("timestamp", 1).limit(limit)
    return [serialize_doc(d) for d in cur]


def cancel_job(job_id: str) -> Dict[str, Any]:
    jobs_col.update_one({"_id": oid(job_id)}, {"$set": {"cancel_requested": True}})
    with _proc_lock:
        proc = _processes.get(job_id)
    if proc and proc.poll() is None:
        proc.terminate()
        _append_log(job_id, "WARN", "Cancel signal sent.")
    return {"jobId": job_id, "status": "cancelling"}


def delete_job(job_id: str) -> Dict[str, Any]:
    job_doc = jobs_col.find_one({"_id": oid(job_id)})

    with _proc_lock:
        proc = _processes.get(job_id)
    if proc and proc.poll() is None:
        proc.terminate()
        _append_log(job_id, "WARN", "Delete requested. Process terminated.")

    file_candidates = set()
    if job_doc:
        for p in job_doc.get("output_files", []) or []:
            if isinstance(p, str) and p:
                file_candidates.add(_to_abs_path(p))
        for p in (job_doc.get("artifacts", {}) or {}).values():
            if isinstance(p, str) and p:
                file_candidates.add(_to_abs_path(p))

    for path in file_candidates:
        try:
            if os.path.isfile(path):
                os.remove(path)
        except Exception:
            pass

    jobs_col.delete_one({"_id": oid(job_id)})
    job_logs_col.delete_many({"job_id": job_id})
    return {"jobId": job_id, "deleted": True}


def _get_config_token(config_id: str) -> Optional[str]:
    if not config_id:
        return None
    cfg = configs_col.find_one({"_id": oid(config_id)}, {"access_token": 1})
    return (cfg or {}).get("access_token")


def _rebuild_job_command(job_doc: Dict[str, Any]) -> tuple[List[str], Dict[str, str]]:
    job_type = job_doc.get("type")
    payload = job_doc.get("payload", {}) or {}
    config_id = str(job_doc.get("config_id") or "")

    if job_type == "explorer":
        token = _get_config_token(config_id)
        bm_id = payload.get("bmId")
        if not token or not bm_id:
            raise RuntimeError("Missing token or bmId for explorer rerun")
        return explorer_command(bm_id, token)

    if job_type == "bulk_clone":
        token = _get_config_token(config_id)
        campaign_id = payload.get("campaignId")
        if not token or not campaign_id:
            raise RuntimeError("Missing token or campaignId for bulk_clone rerun")
        return bulk_clone_command(campaign_id, token)

    if job_type == "single_clone":
        token = _get_config_token(config_id)
        campaign_ids = payload.get("campaignIds", [])
        copies_to_create = int(payload.get("copiesToCreate", 49) or 49)
        if not token or not campaign_ids:
            raise RuntimeError("Missing token or campaignIds for single_clone rerun")
        return single_clone_command(campaign_ids, token, copies_to_create=copies_to_create)

    if job_type == "delete_campaigns":
        token = _get_config_token(config_id)
        campaign_ids = payload.get("campaignIds", [])
        batch = int(payload.get("batch", 10) or 10)
        if not token or not campaign_ids:
            raise RuntimeError("Missing token or campaignIds for delete_campaigns rerun")
        return delete_campaigns_command(campaign_ids, token, batch=batch)

    if job_type == "campaign_status":
        token = _get_config_token(config_id)
        campaign_ids = payload.get("campaignIds", [])
        status = payload.get("status")
        api_version = payload.get("apiVersion", "v21.0")
        if not token or not campaign_ids or not status:
            raise RuntimeError("Missing token/campaignIds/status for campaign_status rerun")
        return campaign_status_command(campaign_ids, token, status=status, api_version=api_version)

    if job_type == "reduce_budgets":
        token = _get_config_token(config_id)
        campaign_ids = payload.get("campaignIds", [])
        execute = bool(payload.get("execute", False))
        min_spend = float(payload.get("minSpend", 5.0) or 5.0)
        target_budget = float(payload.get("targetBudget", 1.0) or 1.0)
        if not token or not campaign_ids:
            raise RuntimeError("Missing token/campaignIds for reduce_budgets rerun")
        return reduce_budgets_command(
            token=token,
            campaign_ids=campaign_ids,
            execute=execute,
            min_spend=min_spend,
            target_budget=target_budget,
        )

    raise RuntimeError(f"Unsupported job type for rerun: {job_type}")


def rerun_job(job_id: str) -> Dict[str, Any]:
    job_doc = jobs_col.find_one({"_id": oid(job_id)})
    if not job_doc:
        raise RuntimeError("Job not found")

    cmd, artifacts = _rebuild_job_command(job_doc)
    return create_job(
        job_type=job_doc.get("type", "unknown"),
        config_id=job_doc.get("config_id", ""),
        payload=job_doc.get("payload", {}) or {},
        cmd=cmd,
        artifacts=artifacts,
    )
