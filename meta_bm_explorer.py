#!/usr/bin/env python3
"""META BM EXPLORER
Recibe el ID de un Business Manager y lista todas las cuentas de ads con sus campañas (nombre e ID).
"""

import argparse
import io
import json
import sys

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

API_VER = "v23.0"
BASE_URL = f"https://graph.facebook.com/{API_VER}"

# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────
parser = argparse.ArgumentParser(description="META BM EXPLORER")
parser.add_argument("--bm-id",        required=True, help="ID del Business Manager")
parser.add_argument("--access-token", required=True, help="Access token de Meta")
parser.add_argument("--output-json",  default=None,  help="(Opcional) Ruta de archivo .json para guardar el resultado")
args = parser.parse_args()

BM_ID        = args.bm_id
ACCESS_TOKEN = args.access_token


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def _get(url: str, params: dict) -> dict:
    """GET con manejo básico de errores."""
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(data["error"].get("message", "API error"))
    return data


def paginate(url: str, params: dict) -> list:
    """Recorre todas las páginas de un endpoint paginado."""
    results = []
    while url:
        data = _get(url, params)
        results.extend(data.get("data", []))
        url    = data.get("paging", {}).get("next")
        params = {}          # next ya incluye todos los params en la URL
    return results


# ──────────────────────────────────────────────
# LÓGICA PRINCIPAL
# ──────────────────────────────────────────────

def get_ad_accounts(bm_id: str) -> list:
    """Devuelve las cuentas de ads propias Y las compartidas (clientes) del BM."""
    common_params = {
        "fields":       "id,name,account_status",
        "access_token": ACCESS_TOKEN,
        "limit":        200,
    }

    owned  = paginate(f"{BASE_URL}/{bm_id}/owned_ad_accounts",  dict(common_params))
    client = paginate(f"{BASE_URL}/{bm_id}/client_ad_accounts", dict(common_params))

    # Marcar origen y deduplicar por id (owned tiene prioridad)
    seen = {}
    for acc in owned:
        acc["_origen"] = "owned"
        seen[acc["id"]] = acc
    for acc in client:
        if acc["id"] not in seen:
            acc["_origen"] = "client"
            seen[acc["id"]] = acc

    return list(seen.values())


def get_campaigns(account_id: str) -> list:
    """Devuelve las campañas de una cuenta de ads."""
    url    = f"{BASE_URL}/{account_id}/campaigns"
    params = {
        "fields":       "id,name,status,objective",
        "access_token": ACCESS_TOKEN,
        "limit":        200,
    }
    return paginate(url, params)


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print(f"  BM ID: {BM_ID}")
    print(f"{'='*60}\n")

    ad_accounts = get_ad_accounts(BM_ID)

    if not ad_accounts:
        print("[!] No se encontraron cuentas de ads para este BM.")
        sys.exit(0)

    result = []

    for account in ad_accounts:
        acc_id     = account["id"]
        acc_name   = account.get("name", "(sin nombre)")
        acc_status = account.get("account_status", "?")
        origen     = account.get("_origen", "?")

        print(f"  CUENTA: {acc_name}  [{acc_id}]  (status: {acc_status})  [{origen}]")

        campaigns = get_campaigns(acc_id)

        campaigns_out = []
        if not campaigns:
            print("    (sin campañas)")
        else:
            for camp in campaigns:
                print(f"    - [{camp['id']}]  {camp.get('name', '(sin nombre)')}  ({camp.get('status','?')})")
                campaigns_out.append({
                    "id":        camp["id"],
                    "name":      camp.get("name"),
                    "status":    camp.get("status"),
                    "objective": camp.get("objective"),
                })

        result.append({
            "account_id":   acc_id,
            "account_name": acc_name,
            "status":       acc_status,
            "origen":       origen,
            "campaigns":    campaigns_out,
        })

        print()

    print(f"{'='*60}")
    print(f"  Total cuentas: {len(result)}")
    print(f"  Total campañas: {sum(len(a['campaigns']) for a in result)}")
    print(f"{'='*60}\n")

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[+] Resultado guardado en: {args.output_json}")

    return result


if __name__ == "__main__":
    main()
