from __future__ import annotations

from datetime import datetime
from typing import Dict, List

import requests


API_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}/"
CHECKOUT_ACTION = "offsite_conversion.fb_pixel_initiate_checkout"
PURCHASE_ACTION = "offsite_conversion.fb_pixel_purchase"
SALE_VALUE = 85.0


def _api_get(endpoint: str, token: str, params: dict | None = None) -> dict:
    url = BASE_URL + endpoint
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, params=params or {}, timeout=35)
    r.raise_for_status()
    return r.json()


def _paginate(endpoint: str, token: str, params: dict | None = None) -> List[dict]:
    data = _api_get(endpoint, token, params)
    rows = list(data.get("data", []))
    paging = data.get("paging", {})
    headers = {"Authorization": f"Bearer {token}"}
    while "next" in paging:
        r = requests.get(paging["next"], headers=headers, timeout=35)
        r.raise_for_status()
        page = r.json()
        rows.extend(page.get("data", []))
        paging = page.get("paging", {})
    return rows


def discover_bm_accounts(bm_id: str, token: str) -> List[dict]:
    common = {"fields": "id,name,account_status,currency", "limit": 200}
    owned = _paginate(f"{bm_id}/owned_ad_accounts", token, common)
    client = _paginate(f"{bm_id}/client_ad_accounts", token, common)

    seen: Dict[str, dict] = {}
    for acc in owned:
        aid = str(acc.get("id", ""))
        if not aid:
            continue
        seen[aid] = {
            "account_id": aid if aid.startswith("act_") else f"act_{aid}",
            "account_name": acc.get("name", aid),
            "account_status": acc.get("account_status", "?"),
            "currency": acc.get("currency", ""),
            "source": "owned",
        }
    for acc in client:
        aid = str(acc.get("id", ""))
        if not aid or aid in seen:
            continue
        seen[aid] = {
            "account_id": aid if aid.startswith("act_") else f"act_{aid}",
            "account_name": acc.get("name", aid),
            "account_status": acc.get("account_status", "?"),
            "currency": acc.get("currency", ""),
            "source": "client",
        }
    return list(seen.values())


def _extract_action(actions: list | None, action_type: str) -> float:
    if not actions:
        return 0.0
    for item in actions:
        if item.get("action_type") == action_type:
            try:
                return float(item.get("value", 0) or 0)
            except Exception:
                return 0.0
    return 0.0


def _fetch_account_rows(account: dict, token: str, date_preset: str) -> List[dict]:
    insights = _paginate(
        f"{account['account_id']}/insights",
        token,
        {
            "fields": "spend,actions,purchase_roas",
            "date_preset": date_preset,
            "limit": 1,
        },
    )
    if not insights:
        return []

    row = insights[0]
    spend = float(row.get("spend", 0) or 0)
    purchases = int(_extract_action(row.get("actions"), PURCHASE_ACTION))
    roas = 0.0
    for ri in row.get("purchase_roas", []):
        if ri.get("action_type") == "omni_purchase":
            try:
                roas = float(ri.get("value", 0) or 0)
            except Exception:
                roas = 0.0
            break
    revenue = round(spend * roas, 2)
    co = int(_extract_action(row.get("actions"), CHECKOUT_ACTION))
    cpa = round(spend / purchases, 2) if purchases > 0 else 0.0
    roi_ratio = ((revenue - spend) / spend) if spend > 0 else 0.0

    return [
        {
            "id": f"{account['account_id']}:{date_preset}",
            "name": account["account_name"],
            "status": "ACTIVE",
            "days": -1,
            "spend_today": round(spend, 2) if date_preset == "today" else 0.0,
            "purchases_today": purchases if date_preset == "today" else 0,
            "co_today": co if date_preset == "today" else 0,
            "cpa_co_today": cpa if date_preset == "today" else 0.0,
            "spend_lt": round(spend, 2) if date_preset == "maximum" else 0.0,
            "purchases_lt": purchases if date_preset == "maximum" else 0,
            "cost_purchase": cpa if date_preset == "maximum" else 0.0,
            "co_lt": co if date_preset == "maximum" else 0,
            "cpa_co_lt": cpa if date_preset == "maximum" else 0.0,
            "hookrate": "-",
            "cpc": 0.0,
            "cpm": 0.0,
            "roi": round(roi_ratio, 3),
            "verdict": "Review",
            "bm": account.get("source", "owned").upper(),
            "revenue": revenue,
            "profit": round(revenue - spend, 2),
            "purchases": purchases,
            "spend": round(spend, 2),
        }
    ]


def _build_summary(rows: List[dict]) -> dict:
    total_spend = sum(float(r.get("spend", 0) or 0) for r in rows)
    total_revenue = sum(float(r.get("revenue", 0) or 0) for r in rows)
    total_purchases = sum(int(r.get("purchases", 0) or 0) for r in rows)
    roi = ((total_revenue - total_spend) / total_spend * 100.0) if total_spend > 0 else 0.0
    return {
        "campaigns": len(rows),
        "spend": round(total_spend, 2),
        "revenue": round(total_revenue, 2),
        "purchases": int(total_purchases),
        "roi": round(roi, 2),
    }


def build_daily_report_snapshot(config_id: str, bm_id: str, token: str, periods: List[str] | None = None) -> dict:
    wanted = periods or ["today", "yesterday", "lifetime"]
    valid = [p for p in wanted if p in ("today", "yesterday", "lifetime")]
    if not valid:
        valid = ["today", "yesterday", "lifetime"]

    date_map = {"today": "today", "yesterday": "yesterday", "lifetime": "last_30d"}

    accounts = discover_bm_accounts(bm_id, token)
    periods_payload: Dict[str, dict] = {}

    for period in valid:
        rows: List[dict] = []
        for acc in accounts:
            try:
                rows.extend(_fetch_account_rows(acc, token, date_map[period]))
            except Exception:
                continue
        rows.sort(key=lambda x: x.get("spend", 0), reverse=True)
        periods_payload[period] = {
            "summary": _build_summary(rows),
            "rows": rows,
        }

    return {
        "config_id": config_id,
        "bm_id": bm_id,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "timezone": "America/Bogota",
        "periods": periods_payload,
        "meta": {
            "accounts_count": len(accounts),
            "sale_value": SALE_VALUE,
            "source": "meta_api_live",
        },
    }
