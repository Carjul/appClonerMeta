import json
from typing import Dict, List

import requests

from app.utils import now_iso

API_VERSION = "v21.0"
BASE = f"https://graph.facebook.com/{API_VERSION}/"

METRIC_TO_META = {
    "cpc": "cpc",
    "cpm": "cpm",
    "cpa_checkout": "cost_per_action_type:offsite_conversion.fb_pixel_InitiateCheckout",
    "cpa_purchase": "cost_per_action_type:offsite_conversion.fb_pixel_Purchase",
    "spend": "spent",
    "purchases": "actions:offsite_conversion.fb_pixel_Purchase",
    "checkouts": "actions:offsite_conversion.fb_pixel_InitiateCheckout",
    "days_running": "hours_since_creation",
}

OP_TO_META = {
    ">": "GREATER_THAN",
    ">=": "GREATER_THAN",
    "<": "LESS_THAN",
    "<=": "LESS_THAN",
    "==": "EQUAL",
}

TIME_RANGE_META = {
    "today": "TODAY",
    "last_3d": "LAST_3_DAYS",
    "last_7d": "LAST_7_DAYS",
    "lifetime": "LIFETIME",
}

FREQ_META = {
    "30min": "SEMI_HOURLY",
    "1h": "HOURLY",
    "4h": "EVERY_4_HOURS",
    "6h": "EVERY_6_HOURS",
    "12h": "EVERY_12_HOURS",
    "24h": "DAILY",
}


def api_get(ep: str, token: str, params: dict | None = None) -> dict:
    r = requests.get(
        BASE + ep,
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=35,
    )
    r.raise_for_status()
    return r.json()


def api_post(ep: str, token: str, data: dict | None = None) -> dict:
    r = requests.post(
        BASE + ep,
        headers={"Authorization": f"Bearer {token}"},
        data=data or {},
        timeout=35,
    )
    r.raise_for_status()
    return r.json()


def api_delete(ep: str, token: str) -> dict:
    r = requests.delete(BASE + ep, headers={"Authorization": f"Bearer {token}"}, timeout=35)
    r.raise_for_status()
    return r.json()


def _paginate(ep: str, token: str, params: dict | None = None) -> List[dict]:
    first = api_get(ep, token, params)
    rows = list(first.get("data", []))
    paging = first.get("paging", {})
    headers = {"Authorization": f"Bearer {token}"}
    while paging.get("next"):
        r = requests.get(paging["next"], headers=headers, timeout=35)
        r.raise_for_status()
        page = r.json()
        rows.extend(page.get("data", []))
        paging = page.get("paging", {})
    return rows


def get_accounts_for_bm(bm_id: str, token: str) -> List[dict]:
    common = {"fields": "id,name,account_status,currency", "limit": 200}
    owned = _paginate(f"{bm_id}/owned_ad_accounts", token, common)
    client = _paginate(f"{bm_id}/client_ad_accounts", token, common)

    seen: Dict[str, dict] = {}
    for src, rows in (("BM1", owned), ("BM2", client)):
        for a in rows:
            aid_raw = str(a.get("id", ""))
            if not aid_raw:
                continue
            aid = aid_raw if aid_raw.startswith("act_") else f"act_{aid_raw}"
            if aid in seen:
                continue
            seen[aid] = {
                "id": aid,
                "name": a.get("name", aid),
                "bm": src,
                "account_status": a.get("account_status"),
                "currency": a.get("currency"),
            }
    return sorted(seen.values(), key=lambda x: (x.get("bm", ""), x.get("name", "")))


def get_campaigns(account_id: str, token: str, status: str = "ACTIVE") -> List[dict]:
    params = {
        "fields": "id,name,status,effective_status",
        "filtering": json.dumps([
            {"field": "effective_status", "operator": "IN", "value": [status]},
        ]),
        "limit": 500,
    }
    return api_get(f"{account_id}/campaigns", token, params).get("data", [])


def create_meta_rule(account_id: str, token: str, rule: dict) -> dict:
    name = rule["name"]

    if rule["type"] == "schedule":
        exec_type = "PAUSE_CAMPAIGN" if rule["action"] == "PAUSE" else "UNPAUSE_CAMPAIGN"
        start_min = int(rule["hour"]) * 60 + int(rule.get("min", 0))
        payload = {
            "name": name,
            "evaluation_spec": json.dumps(
                {
                    "evaluation_type": "SCHEDULE",
                    "filters": [
                        {"field": "entity_type", "value": "CAMPAIGN", "operator": "EQUAL"},
                        {"field": "id", "value": rule["campaign_ids"], "operator": "IN"},
                    ],
                }
            ),
            "execution_spec": json.dumps({"execution_type": exec_type}),
            "schedule_spec": json.dumps(
                {
                    "schedule_type": "CUSTOM",
                    "schedule": [
                        {
                            "days": [0, 1, 2, 3, 4, 5, 6],
                            "start_minute": start_min,
                            "end_minute": start_min,
                        }
                    ],
                }
            ),
        }
    elif rule["type"] == "condition":
        exec_type = "PAUSE_ADSET" if rule["action"] == "PAUSE" else "UNPAUSE_ADSET"
        time_preset = TIME_RANGE_META.get(rule.get("time_range", "last_3d"), "LAST_3_DAYS")
        freq = FREQ_META.get(rule.get("check_freq", "30min"), "SEMI_HOURLY")
        filters = [
            {"field": "entity_type", "value": "ADSET", "operator": "EQUAL"},
            {"field": "campaign.id", "value": rule["campaign_ids"], "operator": "IN"},
            {"field": "time_preset", "value": time_preset, "operator": "EQUAL"},
        ]
        for cond in rule.get("conditions", []):
            metric = cond["metric"]
            meta_field = METRIC_TO_META.get(metric, metric)
            meta_op = OP_TO_META.get(cond["op"], "GREATER_THAN")
            val = cond["val"]
            if metric == "days_running":
                val = float(val) * 24.0
            filters.append({"field": meta_field, "value": val, "operator": meta_op})
        payload = {
            "name": name,
            "evaluation_spec": json.dumps({"evaluation_type": "SCHEDULE", "filters": filters}),
            "execution_spec": json.dumps({"execution_type": exec_type}),
            "schedule_spec": json.dumps({"schedule_type": freq}),
        }
    else:
        raise RuntimeError("Unknown rule type")

    return api_post(f"{account_id}/adrules_library", token, data=payload)


def toggle_meta_rule(meta_rule_id: str, token: str, enabled: bool) -> dict:
    return api_post(meta_rule_id, token, data={"status": "ENABLED" if enabled else "PAUSED"})


def delete_meta_rule(meta_rule_id: str, token: str) -> dict:
    return api_delete(meta_rule_id, token)


def build_log(config_id: str, rule_name: str, action: str, ok: bool, detail: str, account_name: str) -> dict:
    return {
        "config_id": config_id,
        "timestamp": now_iso(),
        "rule": rule_name,
        "action": action,
        "ok": ok,
        "detail": detail,
        "account": account_name,
    }
