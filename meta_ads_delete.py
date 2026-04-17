#!/usr/bin/env python3
"""META ADS DELETE v1.1
Script para DELETE de ads o campanas con reintentos y reporte.

Uso:
  python meta_ads_delete.py --ad-ids <ID1> <ID2> --access-token <TOKEN>
  python meta_ads_delete.py --campaign-ids <ID1> <ID2> --access-token <TOKEN>
  python meta_ads_delete.py --json <archivo.json> --access-token <TOKEN>
"""

import argparse
import io
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_parser = argparse.ArgumentParser(description="META ADS DELETE")
_parser.add_argument("--ad-ids", nargs="*", default=[], help="IDs de ads a eliminar (directos)")
_parser.add_argument("--campaign-ids", nargs="*", default=[], help="IDs de campanas a eliminar (directos)")
_parser.add_argument("--json", help="Archivo JSON con lista de IDs")
_parser.add_argument("--access-token", required=True, help="Access token de Meta Ads")
_parser.add_argument("--batch", type=int, default=10, help="Tamano de batch (default: 10)")
_args = _parser.parse_args()

ACCESS_TOKEN = _args.access_token
BATCH_SIZE = _args.batch
SLEEP_BETWEEN = 1.0

API_VER = "v21.0"
BASE_URL = f"https://graph.facebook.com/{API_VER}"

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
REPORT_FILE = os.path.join(LOG_DIR, f"delete_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

ITEM_IDS = []
TARGET_TYPE = "ad"

if _args.ad_ids:
    ITEM_IDS = _args.ad_ids
    TARGET_TYPE = "ad"
elif _args.campaign_ids:
    ITEM_IDS = _args.campaign_ids
    TARGET_TYPE = "campaign"
elif _args.json:
    if not os.path.exists(_args.json):
        print(f"[ERROR] Archivo no encontrado: {_args.json}")
        sys.exit(1)
    with open(_args.json, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        ITEM_IDS = data
    elif isinstance(data, dict):
        keys_map = [
            ("campaigns_to_delete", "campaign"),
            ("campaigns", "campaign"),
            ("campaign_ids", "campaign"),
            ("ads_to_delete", "ad"),
            ("ads", "ad"),
            ("ad_ids", "ad"),
            ("ids", "ad"),
        ]
        for key, kind in keys_map:
            if key in data:
                ITEM_IDS = data[key]
                TARGET_TYPE = kind
                break
        if not ITEM_IDS:
            ITEM_IDS = list(data.values())[0] if data else []
else:
    print("[ERROR] Proporciona --ad-ids, --campaign-ids o --json")
    sys.exit(1)

if not ITEM_IDS:
    print("[ERROR] No hay elementos para eliminar")
    sys.exit(1)


def api_batch_delete(ids_batch):
    batch_requests = [{"method": "DELETE", "relative_url": item_id} for item_id in ids_batch]
    attempt = 0
    while True:
        try:
            r = requests.post(
                f"{BASE_URL}/",
                timeout=60,
                data={"access_token": ACCESS_TOKEN, "batch": json.dumps(batch_requests)},
            )
            raw_results = r.json()
        except Exception as e:
            print(f"\n  [NET] {e}")
            time.sleep(5)
            continue

        if isinstance(raw_results, dict) and "error" in raw_results:
            err = raw_results["error"]
            if err.get("code") in (4, 17, 32, 613, 500, 502, 503, 504):
                wait = min(2 ** attempt * 5, 120)
                print(f" [RL:{wait}s]", end="", flush=True)
                time.sleep(wait)
                attempt += 1
                continue
            raise RuntimeError(f"Batch error: {err.get('message')}")

        results = []
        for idx, item in enumerate(raw_results):
            item_id = ids_batch[idx]
            try:
                body = json.loads(item.get("body", "{}")) if isinstance(item.get("body"), str) else item.get("body", {})
            except Exception:
                body = {}
            results.append(
                {
                    "item_id": item_id,
                    "code": item.get("code", 0),
                    "body": body,
                    "success": item.get("code", 0) == 200 or body.get("success", False),
                }
            )
        return results


def clog(level, message):
    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    print(f"{ts} | {level:<6} | {message}")


def main():
    print("=" * 70)
    print("  META ADS DELETE v1.1")
    print("=" * 70)
    print(f"  Tipo: {TARGET_TYPE}")
    print(f"  Total a eliminar: {len(ITEM_IDS)}")
    print(f"  Batch size: {BATCH_SIZE}")
    print()

    report = {"target_type": TARGET_TYPE, "total": len(ITEM_IDS), "deleted": 0, "failed": 0, "results": []}

    for batch_num in range(0, len(ITEM_IDS), BATCH_SIZE):
        batch = ITEM_IDS[batch_num : batch_num + BATCH_SIZE]
        batch_idx = (batch_num // BATCH_SIZE) + 1
        total_batches = (len(ITEM_IDS) + BATCH_SIZE - 1) // BATCH_SIZE

        print(f"\n[{batch_idx}/{total_batches}] Eliminando {len(batch)} {TARGET_TYPE}s...", end="", flush=True)
        try:
            results = api_batch_delete(batch)
            print(" OK")
            for result in results:
                if result["success"]:
                    clog("OK", f"Deleted {TARGET_TYPE}: {result['item_id']}")
                    report["deleted"] += 1
                else:
                    err_obj = result["body"].get("error", {})
                    error_msg = err_obj.get("message", "Unknown error") if isinstance(err_obj, dict) else str(err_obj)
                    clog("ERROR", f"Failed {TARGET_TYPE} {result['item_id']}: {error_msg}")
                    report["failed"] += 1
                    report["results"].append({"item_id": result["item_id"], "status": "FAILED", "error": error_msg})
                time.sleep(SLEEP_BETWEEN / max(1, len(batch)))
        except Exception as e:
            clog("ERROR", f"Batch {batch_idx} failed: {str(e)}")
            for item_id in batch:
                report["failed"] += 1
                report["results"].append({"item_id": item_id, "status": "BATCH_ERROR", "error": str(e)})

    print(f"\n{'=' * 70}")
    print("RESUMEN")
    print(f"{'=' * 70}")
    print(f"  Total   : {report['total']}")
    print(f"  Deleted : {report['deleted']} OK")
    print(f"  Failed  : {report['failed']}")

    if report["deleted"] == report["total"]:
        print(f"\n  COMPLETO - Todos los {TARGET_TYPE}s eliminados")
    elif report["deleted"] > 0:
        print(f"\n  PARCIAL - {report['failed']} {TARGET_TYPE}s requieren atencion manual")
    else:
        print(f"\n  FALLO - Ningun {TARGET_TYPE} se pudo eliminar")

    print(f"\n  Report: {REPORT_FILE}")
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
