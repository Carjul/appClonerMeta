#!/usr/bin/env python3
"""FB Optimizer - Budget reduction by selected campaigns.

Usage:
  python reduce_budgets.py --access-token TOKEN --campaign-ids 123 456
  python reduce_budgets.py --access-token TOKEN --campaign-ids 123 456 --execute
"""

import argparse
import io
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _safe_print(*args, **kwargs):
    sep = kwargs.pop("sep", " ")
    end = kwargs.pop("end", "\n")
    file = kwargs.pop("file", sys.stdout)
    flush = kwargs.pop("flush", False)
    text = sep.join(str(a) for a in args)
    text = text.encode("ascii", "replace").decode("ascii")
    file.write(text + end)
    if flush:
        file.flush()


print = _safe_print


API_BASE = "https://graph.facebook.com/v21.0"
TARGET_BUDGET_CENTS = 100
BUMP_BUDGET_CENTS = 105
MIN_SPEND_TO_REDUCE = 5.0
MIN_AGE_HOURS = 48
HTTP_TIMEOUT = 30
NETWORK_RETRIES = 3


def api_get(path: str, token: str, params: dict | None = None) -> dict:
    url = f"{API_BASE}/{path}"
    if params:
        url += "?" + urlencode(params)
    separator = "&" if "?" in url else "?"
    url += f"{separator}access_token={token}"

    req = Request(url, method="GET")
    for attempt in range(NETWORK_RETRIES + 1):
        try:
            with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            body = e.read().decode() if e.fp else ""
            print(f"  WARN API Error {e.code} en GET {path}: {body[:200]}")
            if e.code in (429, 500, 502, 503, 504) and attempt < NETWORK_RETRIES:
                time.sleep(1.5 * (attempt + 1))
                continue
            return {}
        except (URLError, TimeoutError, OSError) as e:
            if attempt < NETWORK_RETRIES:
                wait = 1.5 * (attempt + 1)
                print(f"  WARN NET Error GET {path}: {e} (retry {attempt + 1}/{NETWORK_RETRIES}, wait {wait:.1f}s)")
                time.sleep(wait)
                continue
            print(f"  WARN NET Error GET {path}: {e}")
            return {}
        except Exception as e:
            print(f"  WARN Unexpected GET {path}: {e}")
            return {}
    return {}


def api_post(endpoint: str, token: str, data: dict) -> dict:
    url = f"{API_BASE}/{endpoint}"
    payload = dict(data)
    payload["access_token"] = token
    encoded = urlencode(payload).encode()

    req = Request(url, data=encoded, method="POST")
    for attempt in range(NETWORK_RETRIES + 1):
        try:
            with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            body = e.read().decode() if e.fp else ""
            print(f"  WARN API Error {e.code} en POST {endpoint}: {body[:200]}")
            if e.code in (429, 500, 502, 503, 504) and attempt < NETWORK_RETRIES:
                time.sleep(1.5 * (attempt + 1))
                continue
            return {}
        except (URLError, TimeoutError, OSError) as e:
            if attempt < NETWORK_RETRIES:
                wait = 1.5 * (attempt + 1)
                print(f"  WARN NET Error POST {endpoint}: {e} (retry {attempt + 1}/{NETWORK_RETRIES}, wait {wait:.1f}s)")
                time.sleep(wait)
                continue
            print(f"  WARN NET Error POST {endpoint}: {e}")
            return {}
        except Exception as e:
            print(f"  WARN Unexpected POST {endpoint}: {e}")
            return {}
    return {}


def get_campaign(campaign_id: str, token: str) -> dict:
    fields = "id,name,account_id,created_time,status,effective_status"
    return api_get(campaign_id, token, {"fields": fields})


def get_active_adsets_by_campaign(campaign_id: str, token: str) -> list:
    fields = "id,name,status,daily_budget,created_time,campaign_id"
    data = api_get(f"{campaign_id}/adsets", token, {"fields": fields, "limit": 500})
    adsets = data.get("data", [])
    return [a for a in adsets if a.get("status") == "ACTIVE"]


def get_adset_insights(adset_id: str, token: str, date_preset: str = "maximum") -> dict:
    fields = "spend,cpc,impressions,actions,cost_per_action_type"
    data = api_get(f"{adset_id}/insights", token, {"fields": fields, "date_preset": date_preset})
    rows = data.get("data", [])
    return rows[0] if rows else {}


def get_adset_today_spend(adset_id: str, token: str) -> float:
    insights = get_adset_insights(adset_id, token, date_preset="today")
    return float(insights.get("spend", 0))


def is_too_young(created_time: str) -> bool:
    try:
        created = datetime.fromisoformat(created_time)
        now = datetime.now(timezone.utc)
        age = now - created
        return age < timedelta(hours=MIN_AGE_HOURS)
    except Exception:
        return True


def reduce_budget(adset_id: str, new_budget_cents: int, token: str) -> dict:
    return api_post(adset_id, token, {"daily_budget": str(new_budget_cents)})


def safe_ascii(text: str) -> str:
    return str(text).encode("ascii", "replace").decode("ascii")


def process_campaign(campaign: dict, token: str, execute: bool) -> list:
    results = []
    campaign_id = str(campaign.get("id", ""))
    campaign_name = campaign.get("name", "(sin nombre)")
    account_raw = str(campaign.get("account_id", ""))
    account_id = account_raw if account_raw.startswith("act_") else f"act_{account_raw}" if account_raw else ""
    campaign_created = campaign.get("created_time", "")

    if not campaign_id:
        return results

    adsets = get_active_adsets_by_campaign(campaign_id, token)
    if not adsets:
        return results

    for adset in adsets:
        adset_id = adset["id"]
        adset_name = adset.get("name", "Sin nombre")
        current_budget = int(adset.get("daily_budget", 0))

        if is_too_young(campaign_created):
            results.append(
                {
                    "account_id": account_id,
                    "campaign_id": campaign_id,
                    "campaign_name": campaign_name,
                    "adset": adset_name,
                    "adset_id": adset_id,
                    "budget_actual": f"${current_budget / 100:.2f}",
                    "accion": "SKIP - campaign < 48 horas",
                    "ejecutado": False,
                }
            )
            continue

        if current_budget > TARGET_BUDGET_CENTS:
            lifetime_insights = get_adset_insights(adset_id, token, "maximum")
            total_spend = float(lifetime_insights.get("spend", 0))
            if total_spend >= MIN_SPEND_TO_REDUCE:
                action = f"REDUCIR ${current_budget / 100:.2f} -> ${TARGET_BUDGET_CENTS / 100:.2f} (gasto ${total_spend:.2f} total)"
                executed = False
                if execute:
                    resp = reduce_budget(adset_id, TARGET_BUDGET_CENTS, token)
                    executed = bool(resp.get("success", False) or resp.get("id"))
                results.append(
                    {
                        "account_id": account_id,
                        "campaign_id": campaign_id,
                        "campaign_name": campaign_name,
                        "adset": adset_name,
                        "adset_id": adset_id,
                        "budget_actual": f"${current_budget / 100:.2f}",
                        "spend_total": f"${total_spend:.2f}",
                        "accion": action,
                        "ejecutado": executed,
                    }
                )
            else:
                results.append(
                    {
                        "account_id": account_id,
                        "campaign_id": campaign_id,
                        "campaign_name": campaign_name,
                        "adset": adset_name,
                        "adset_id": adset_id,
                        "budget_actual": f"${current_budget / 100:.2f}",
                        "spend_total": f"${total_spend:.2f}",
                        "accion": f"ESPERAR - solo gasto ${total_spend:.2f} (min ${MIN_SPEND_TO_REDUCE})",
                        "ejecutado": False,
                    }
                )
            continue

        if current_budget == TARGET_BUDGET_CENTS:
            today_spend = get_adset_today_spend(adset_id, token)
            if today_spend == 0:
                action = f"BUMP ${TARGET_BUDGET_CENTS / 100:.2f} -> ${BUMP_BUDGET_CENTS / 100:.2f} (no gasto hoy)"
                executed = False
                if execute:
                    resp = reduce_budget(adset_id, BUMP_BUDGET_CENTS, token)
                    executed = bool(resp.get("success", False) or resp.get("id"))
                results.append(
                    {
                        "account_id": account_id,
                        "campaign_id": campaign_id,
                        "campaign_name": campaign_name,
                        "adset": adset_name,
                        "adset_id": adset_id,
                        "budget_actual": f"${TARGET_BUDGET_CENTS / 100:.2f}",
                        "spend_hoy": "$0.00",
                        "accion": action,
                        "ejecutado": executed,
                    }
                )

    return results


def main():
    global MIN_SPEND_TO_REDUCE, TARGET_BUDGET_CENTS

    parser = argparse.ArgumentParser(description="FB Optimizer - Reduccion de Budget por campana")
    parser.add_argument("--access-token", required=True, help="Access token de la config seleccionada")
    parser.add_argument("--campaign-ids", nargs="+", required=True, help="Una o varias campanas a procesar")
    parser.add_argument("--execute", action="store_true", help="Aplicar cambios reales (default: dry run)")
    parser.add_argument("--min-spend", type=float, default=MIN_SPEND_TO_REDUCE, help=f"Gasto minimo (default ${MIN_SPEND_TO_REDUCE})")
    parser.add_argument("--target-budget", type=float, default=1.00, help="Budget objetivo USD (default $1.00)")
    parser.add_argument("--output-json", default=None, help="Ruta opcional para guardar resultado JSON")
    args = parser.parse_args()

    MIN_SPEND_TO_REDUCE = max(0.0, float(args.min_spend))
    TARGET_BUDGET_CENTS = max(1, int(float(args.target_budget) * 100))

    mode = "EJECUTANDO" if args.execute else "DRY RUN"
    print(f"\n{'='*60}")
    print(f"  FB Optimizer - Reduccion de Budget [{mode}]")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Campaigns: {len(args.campaign_ids)} | Target: ${TARGET_BUDGET_CENTS/100:.2f}/dia | Min gasto: ${MIN_SPEND_TO_REDUCE:.2f}")
    print(f"{'='*60}\n")

    all_results = []
    for idx, campaign_id in enumerate(args.campaign_ids, 1):
        print(f"[{idx}/{len(args.campaign_ids)}] Procesando campaign {campaign_id}...")
        campaign = get_campaign(campaign_id, args.access_token)
        if not campaign or not campaign.get("id"):
            print(f"  WARN No se pudo leer campaign {campaign_id}")
            continue
        print(f"  Campana: {safe_ascii(campaign.get('name', '(sin nombre)'))}")
        results = process_campaign(campaign, args.access_token, args.execute)
        all_results.extend(results)
        for r in results:
            status = "OK" if r.get("ejecutado") else ".."
            print(f"    {status} {safe_ascii(r.get('adset', ''))[:46]}: {safe_ascii(r.get('accion', ''))}")

    reducidos = [r for r in all_results if "REDUCIR" in r.get("accion", "")]
    bumps = [r for r in all_results if "BUMP" in r.get("accion", "")]
    skips = [r for r in all_results if "SKIP" in r.get("accion", "")]
    esperando = [r for r in all_results if "ESPERAR" in r.get("accion", "")]

    print(f"\n{'='*60}")
    print("  RESUMEN")
    print(f"  Registros analizados: {len(all_results)}")
    print(f"  Reducidos objetivo:   {len(reducidos)}")
    print(f"  Bumps:               {len(bumps)}")
    print(f"  Esperando data:      {len(esperando)}")
    print(f"  Skipped <48h:        {len(skips)}")
    print(f"{'='*60}")

    if not args.execute and (reducidos or bumps):
        print("\n  WARNING: DRY RUN - agrega --execute para aplicar cambios\n")

    output_file = args.output_json
    if not output_file:
        logs_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        output_file = os.path.join(logs_dir, f"budget_reduction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    else:
        parent = os.path.dirname(output_file)
        if parent:
            os.makedirs(parent, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"  Resultados guardados en: {output_file}\n")


if __name__ == "__main__":
    main()
