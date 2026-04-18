#!/usr/bin/env python3
"""
FB Optimizer — Reducción de Budget para Ad Sets
================================================
Recorre todas las ad accounts de ambos BMs, identifica ad sets activos
que cumplen condiciones de reducción, y baja el budget a $1/día.

Uso:
    python reduce_budgets.py --token-bm1 TOKEN1 --token-bm2 TOKEN2 [--execute]

    O con variables de entorno:
    META_BM1_TOKEN=xxx META_BM2_TOKEN=xxx python reduce_budgets.py [--execute]

Modos:
    Sin --execute:  DRY RUN (solo muestra qué haría, no toca nada)
    Con --execute:  Aplica los cambios de budget en Meta

Reglas de reducción:
    1. Ad sets con daily_budget > $1.00 Y spend total >= $5.00 → bajar a $1.00/día
    2. Ad sets "muertos" (budget $1, spend $0 en 24h) → bump a $1.05 (luego manual a $1)
    3. Campañas con < 48 horas de antigüedad → NO SE TOCAN
"""

import argparse
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError

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

# ─── Configuración de cuentas ────────────────────────────────────────────────

BM1_ACCOUNTS = {
    "MARTHA 1":  "act_1037309266927320",  # COP
    "MARTHA 2":  "act_528756616577904",   # USD
    "MARTHA 3":  "act_1474139290589410",  # COP
    "MARTHA 4":  "act_708152401990591",   # USD
    "GM-177":    "act_1027335185283047",  # USD
    "RPG 15":    "act_2121935234933980",  # USD
    "THM-60":    "act_1247132143392586",  # USD
    "THM-32":    "act_1985532452249785",  # USD
    "THM-54":    "act_1594785768155717",  # USD
    "THM-72":    "act_1540233950717702",  # USD
    "THM-113":   "act_1074066461137769",  # USD
    "THM-200":   "act_1059904599553927",  # USD
}

BM2_ACCOUNTS = {
    "DG-03":    "act_1306256300004871",   # USD
    "DG-51":    "act_900364275348331",    # USD
    "MSTC-20":  "act_1239484177480232",   # USD
    "THM-119":  "act_1650693448960867",   # USD
    "KM-19":    "act_2049541032515377",   # USD
    "THM-55":   "act_1654285161902955",   # USD
}

API_BASE = "https://graph.facebook.com/v21.0"
TARGET_BUDGET_CENTS = 100    # $1.00 en centavos
BUMP_BUDGET_CENTS = 105      # $1.05 en centavos (para ad sets que no gastan)
MIN_SPEND_TO_REDUCE = 5.0    # Mínimo $5 de gasto total para aplicar reducción
MIN_AGE_HOURS = 48           # No tocar campañas con menos de 48 horas


# ─── Helpers de API ──────────────────────────────────────────────────────────

def api_get(path: str, token: str, params: dict = None) -> dict:
    """GET request a la Meta Graph API."""
    url = f"{API_BASE}/{path}"
    if params:
        url += "?" + urlencode(params)
    # Agregar token
    separator = "&" if "?" in url else "?"
    url += f"{separator}access_token={token}"

    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"  WARN API Error {e.code} en GET {path}: {body[:200]}")
        return {}


def api_post(endpoint: str, token: str, data: dict) -> dict:
    """POST request a la Meta Graph API."""
    url = f"{API_BASE}/{endpoint}"
    data["access_token"] = token
    encoded = urlencode(data).encode()

    req = Request(url, data=encoded, method="POST")
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"  WARN API Error {e.code} en POST {endpoint}: {body[:200]}")
        return {}


# ─── Lógica principal ────────────────────────────────────────────────────────

def get_active_adsets(account_id: str, token: str) -> list:
    """Obtiene todos los ad sets ACTIVOS de una cuenta con su budget y fecha de creación."""
    fields = "id,name,status,daily_budget,created_time,campaign_id"
    data = api_get(
        f"{account_id}/adsets",
        token,
        {"fields": fields, "limit": 500}
    )
    # Filtrar por status ACTIVE en Python (Meta API no soporta filtering por status)
    adsets = data.get("data", [])
    return [a for a in adsets if a.get("status") == "ACTIVE"]


def get_adset_insights(adset_id: str, token: str, date_preset: str = "maximum") -> dict:
    """Obtiene insights (spend) de un ad set."""
    fields = "spend,cpc,impressions,actions,cost_per_action_type"
    data = api_get(
        f"{adset_id}/insights",
        token,
        {"fields": fields, "date_preset": date_preset}
    )
    results = data.get("data", [])
    return results[0] if results else {}


def get_adset_today_spend(adset_id: str, token: str) -> float:
    """Obtiene el gasto de hoy de un ad set."""
    insights = get_adset_insights(adset_id, token, date_preset="today")
    return float(insights.get("spend", 0))


def is_too_young(created_time: str) -> bool:
    """Verifica si el ad set tiene menos de 48 horas."""
    try:
        # Meta devuelve formato ISO 8601: 2026-04-10T15:30:00-0500
        created = datetime.fromisoformat(created_time)
        now = datetime.now(timezone.utc)
        age = now - created
        return age < timedelta(hours=MIN_AGE_HOURS)
    except (ValueError, TypeError):
        return True  # Si no podemos parsear, no tocar por seguridad


def reduce_budget(adset_id: str, new_budget_cents: int, token: str) -> dict:
    """Cambia el daily_budget de un ad set."""
    return api_post(adset_id, token, {"daily_budget": str(new_budget_cents)})


def safe_ascii(text: str) -> str:
    return str(text).encode("ascii", "replace").decode("ascii")


def process_account(account_name: str, account_id: str, token: str, execute: bool) -> list:
    """Procesa una cuenta: identifica ad sets para reducción."""
    results = []

    adsets = get_active_adsets(account_id, token)
    if not adsets:
        return results

    for adset in adsets:
        adset_id = adset["id"]
        adset_name = adset.get("name", "Sin nombre")
        current_budget = int(adset.get("daily_budget", 0))  # en centavos
        created_time = adset.get("created_time", "")

        # Regla 0: No tocar campañas menores a 48 horas
        if is_too_young(created_time):
            results.append({
                "account": account_name,
                "adset": adset_name,
                "adset_id": adset_id,
                "budget_actual": f"${current_budget / 100:.2f}",
                "accion": "SKIP - < 48 horas",
                "ejecutado": False
            })
            continue

        # Regla 1: Budget > $1.00 y ya gastó >= $5 total → bajar a $1.00
        if current_budget > TARGET_BUDGET_CENTS:
            lifetime_insights = get_adset_insights(adset_id, token, "maximum")
            total_spend = float(lifetime_insights.get("spend", 0))

            if total_spend >= MIN_SPEND_TO_REDUCE:
                action = f"REDUCIR ${current_budget / 100:.2f} -> $1.00 (gasto ${total_spend:.2f} total)"
                executed = False

                if execute:
                    resp = reduce_budget(adset_id, TARGET_BUDGET_CENTS, token)
                    executed = resp.get("success", False)

                results.append({
                    "account": account_name,
                    "adset": adset_name,
                    "adset_id": adset_id,
                    "budget_actual": f"${current_budget / 100:.2f}",
                    "spend_total": f"${total_spend:.2f}",
                    "accion": action,
                    "ejecutado": executed
                })
            else:
                results.append({
                    "account": account_name,
                    "adset": adset_name,
                    "adset_id": adset_id,
                    "budget_actual": f"${current_budget / 100:.2f}",
                    "spend_total": f"${total_spend:.2f}",
                    "accion": f"ESPERAR - solo gasto ${total_spend:.2f} (min ${MIN_SPEND_TO_REDUCE})",
                    "ejecutado": False
                })
            continue

        # Regla 2: Budget = $1.00, spend hoy = $0 → bump a $1.05
        if current_budget == TARGET_BUDGET_CENTS:
            today_spend = get_adset_today_spend(adset_id, token)

            if today_spend == 0:
                action = f"BUMP $1.00 -> $1.05 (no gasto hoy)"
                executed = False

                if execute:
                    resp = reduce_budget(adset_id, BUMP_BUDGET_CENTS, token)
                    executed = resp.get("success", False)

                results.append({
                    "account": account_name,
                    "adset": adset_name,
                    "adset_id": adset_id,
                    "budget_actual": "$1.00",
                    "spend_hoy": "$0.00",
                    "accion": action,
                    "ejecutado": executed
                })

    return results


def main():
    global MIN_SPEND_TO_REDUCE, TARGET_BUDGET_CENTS
    
    parser = argparse.ArgumentParser(
        description="FB Optimizer — Reducción de Budget",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Dry run (solo ver qué haría):
  python reduce_budgets.py --token-bm1 TOKEN1 --token-bm2 TOKEN2

  # Ejecutar cambios:
  python reduce_budgets.py --token-bm1 TOKEN1 --token-bm2 TOKEN2 --execute

  # Solo BM1:
  python reduce_budgets.py --token-bm1 TOKEN1 --execute

  # Con variables de entorno:
  META_BM1_TOKEN=xxx META_BM2_TOKEN=xxx python reduce_budgets.py --execute
        """
    )
    parser.add_argument("--token-bm1", default=os.environ.get("META_BM1_TOKEN", ""),
                        help="Access token para BM1 (o usar META_BM1_TOKEN env var)")
    parser.add_argument("--token-bm2", default=os.environ.get("META_BM2_TOKEN", ""),
                        help="Access token para BM2 (o usar META_BM2_TOKEN env var)")
    parser.add_argument("--execute", action="store_true",
                        help="Ejecutar cambios (sin esto es DRY RUN)")
    parser.add_argument("--min-spend", type=float, default=MIN_SPEND_TO_REDUCE,
                        help=f"Gasto mínimo para aplicar reducción (default: ${MIN_SPEND_TO_REDUCE})")
    parser.add_argument("--target-budget", type=float, default=1.00,
                        help="Budget objetivo en dólares (default: $1.00)")

    args = parser.parse_args()

    if not args.token_bm1 and not args.token_bm2:
        print("Error: Necesitas al menos un token (--token-bm1 o --token-bm2)")
        sys.exit(1)

    # Override globals si el usuario pasó valores custom
    MIN_SPEND_TO_REDUCE = args.min_spend
    TARGET_BUDGET_CENTS = int(args.target_budget * 100)

    mode = "EJECUTANDO" if args.execute else "DRY RUN"
    print(f"\n{'='*60}")
    print(f"  FB Optimizer - Reduccion de Budget [{mode}]")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Target: ${args.target_budget:.2f}/dia | Min gasto: ${args.min_spend:.2f}")
    print(f"{'='*60}\n")

    all_results = []

    # Procesar BM1
    if args.token_bm1:
        print("-- BM1: Martha Lucelly 1 ------------------------------")
        for name, act_id in BM1_ACCOUNTS.items():
            print(f"  Procesando {name} ({act_id})...")
            results = process_account(name, act_id, args.token_bm1, args.execute)
            all_results.extend(results)
            for r in results:
                status = "OK" if r.get("ejecutado") else ".."
                print(f"    {status} {safe_ascii(r.get('adset', ''))[:40]}: {safe_ascii(r.get('accion', ''))}")
        print()

    # Procesar BM2
    if args.token_bm2:
        print("-- BM2: JV Liminal ------------------------------------")
        for name, act_id in BM2_ACCOUNTS.items():
            print(f"  Procesando {name} ({act_id})...")
            results = process_account(name, act_id, args.token_bm2, args.execute)
            all_results.extend(results)
            for r in results:
                status = "OK" if r.get("ejecutado") else ".."
                print(f"    {status} {safe_ascii(r.get('adset', ''))[:40]}: {safe_ascii(r.get('accion', ''))}")
        print()

    # Resumen
    reducidos = [r for r in all_results if "REDUCIR" in r["accion"]]
    bumps = [r for r in all_results if "BUMP" in r["accion"]]
    skips = [r for r in all_results if "SKIP" in r["accion"]]
    esperando = [r for r in all_results if "ESPERAR" in r["accion"]]

    print(f"{'='*60}")
    print(f"  RESUMEN")
    print(f"  Ad sets analizados: {len(all_results)}")
    print(f"  Reducidos a $1.00:  {len(reducidos)}")
    print(f"  Bumps a $1.05:      {len(bumps)}")
    print(f"  Esperando data:     {len(esperando)}")
    print(f"  Skipped (< 48h):    {len(skips)}")
    print(f"{'='*60}")

    if not args.execute and (reducidos or bumps):
        print(f"\n  WARNING: DRY RUN - Agrega --execute para aplicar cambios\n")

    # Exportar resultados a JSON en carpeta logs/
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    output_file_name = f"budget_reduction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_file = os.path.join(logs_dir, output_file_name)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"  Resultados guardados en: {output_file}\n")


if __name__ == "__main__":
    main()
