#!/usr/bin/env python3
"""META BM EXPLORER + CAMPAIGN METRICS
Recibe el ID de un Business Manager y lista cuentas de ads con campañas.
Ahora incluye metricas por campana (today + lifetime) para enriquecer cache/frontend.
"""

import argparse
import io
import json
import math
import sys
import time
from datetime import datetime, timezone

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

API_VER = "v23.0"
BASE_URL = f"https://graph.facebook.com/{API_VER}"
RATE_LIMIT_CODES = {4, 17, 32, 613}
DEFAULT_SALE_VALUE = 85.0


parser = argparse.ArgumentParser(description="META BM EXPLORER")
parser.add_argument("--bm-id", required=True, help="ID del Business Manager")
parser.add_argument("--access-token", required=True, help="Access token de Meta")
parser.add_argument("--output-json", default=None, help="(Opcional) Ruta de archivo .json para guardar el resultado")
parser.add_argument("--with-insights", action="store_true", default=True, help="Incluir metricas de insights por campana")
parser.add_argument("--no-insights", action="store_false", dest="with_insights", help="No incluir metricas (solo id/nombre/status)")
parser.add_argument("--sale-value", type=float, default=DEFAULT_SALE_VALUE, help="Valor promedio de venta para ROI (default: 85)")
args = parser.parse_args()

BM_ID = args.bm_id
ACCESS_TOKEN = args.access_token
WITH_INSIGHTS = args.with_insights
SALE_VALUE = args.sale_value if args.sale_value and args.sale_value > 0 else DEFAULT_SALE_VALUE


def _log(msg: str) -> None:
    print(msg, flush=True)


def _request_get(url: str, params: dict | None = None, timeout: int = 30) -> dict:
    retries = 6
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params or {}, timeout=timeout)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and data.get("error"):
                    err = data["error"]
                    code = int(err.get("code", 0) or 0)
                    if code in RATE_LIMIT_CODES and attempt < retries - 1:
                        wait = min(2 ** attempt, 32)
                        _log(f"[WARN] Rate limit code={code}. Retry in {wait}s...")
                        time.sleep(wait)
                        continue
                    raise RuntimeError(f"API Error [{code}]: {err.get('message', 'Unknown')} | type: {err.get('type', '?')}")
                return data

            err_data = {}
            try:
                err_data = r.json().get("error", {})
            except Exception:
                pass

            code = int(err_data.get("code", 0) or 0)
            if (r.status_code >= 500 or code in RATE_LIMIT_CODES) and attempt < retries - 1:
                wait = min(2 ** attempt, 32)
                _log(f"[WARN] HTTP {r.status_code} code={code}. Retry in {wait}s...")
                time.sleep(wait)
                continue

            if err_data:
                raise RuntimeError(
                    f"API Error [{code}]: {err_data.get('message')} | type: {err_data.get('type')} | fbtrace: {err_data.get('fbtrace_id')}"
                )
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")
        except requests.RequestException as e:
            if attempt < retries - 1:
                wait = min(2 ** attempt, 32)
                _log(f"[WARN] Network error: {e}. Retry in {wait}s...")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Network error: {e}")

    raise RuntimeError("Request retries exhausted")


def paginate(url: str, params: dict) -> list:
    results = []
    while url:
        data = _request_get(url, params)
        results.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        params = {}
        time.sleep(0.05)
    return results


def get_ad_accounts(bm_id: str) -> list:
    common_params = {
        "fields": "id,name,account_status,currency",
        "access_token": ACCESS_TOKEN,
        "limit": 200,
    }
    owned = paginate(f"{BASE_URL}/{bm_id}/owned_ad_accounts", dict(common_params))
    client = paginate(f"{BASE_URL}/{bm_id}/client_ad_accounts", dict(common_params))

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
    url = f"{BASE_URL}/{account_id}/campaigns"
    params = {
        "fields": "id,name,status,effective_status,objective,created_time,daily_budget,lifetime_budget",
        "access_token": ACCESS_TOKEN,
        "limit": 200,
    }
    return paginate(url, params)


def get_adset_daily_budget_sum_by_campaign(account_id: str) -> dict:
    """Fallback for ABO campaigns: sum active adset daily budgets by campaign."""
    url = f"{BASE_URL}/{account_id}/adsets"
    params = {
        "fields": "id,campaign_id,status,daily_budget",
        "access_token": ACCESS_TOKEN,
        "limit": 200,
    }
    adsets = paginate(url, params)
    out = {}
    for ad in adsets:
        if ad.get("status") != "ACTIVE":
            continue
        cid = ad.get("campaign_id")
        if not cid:
            continue
        cents = _safe_float(ad.get("daily_budget"))
        if cents <= 0:
            continue
        out[cid] = out.get(cid, 0.0) + cents
    for cid in list(out.keys()):
        out[cid] = round(out[cid] / 100.0, 4)
    return out


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _extract_action(actions_list, action_type):
    if not actions_list:
        return 0.0
    for action in actions_list:
        if action.get("action_type") == action_type:
            try:
                return float(action.get("value", 0) or 0)
            except Exception:
                return 0.0
    return 0.0


def _extract_cost_per_action(cost_list, action_type):
    if not cost_list:
        return 0.0
    for item in cost_list:
        if item.get("action_type") == action_type:
            try:
                return float(item.get("value", 0) or 0)
            except Exception:
                return 0.0
    return 0.0


def _calculate_days_live(created_time_str):
    if not created_time_str:
        return -1
    try:
        created = datetime.fromisoformat(created_time_str.replace("+0000", "+00:00"))
        now = datetime.now(timezone.utc)
        return max(0, (now - created).days)
    except Exception:
        return -1


def _calculate_hook_rate(insights):
    video_plays = insights.get("video_play_actions", []) if isinstance(insights, dict) else []
    try:
        impressions = float((insights or {}).get("impressions", 0) or 0)
    except Exception:
        impressions = 0.0
    if not video_plays or impressions <= 0:
        return None
    views_3s = 0.0
    for vp in video_plays:
        if vp.get("action_type") == "video_view":
            try:
                views_3s = float(vp.get("value", 0) or 0)
            except Exception:
                views_3s = 0.0
            break
    if views_3s <= 0:
        return None
    return (views_3s / impressions) * 100.0


def _determine_verdict(days, spend_lt, cpc, cpa_co_lt, purchases_lt, cost_per_purchase, has_video):
    if days < 2:
        return "New (<48h)"
    if spend_lt < 5:
        return "Insufficient Data"
    if cpa_co_lt > 20 and spend_lt >= 20:
        return "Kill"
    cpc_limit = 1.50 if has_video else 1.00
    if cpc > 0 and cpc > cpc_limit:
        return "High CPC"
    if cpa_co_lt > 0 and cpa_co_lt <= 20 and purchases_lt > 0:
        if cost_per_purchase <= SALE_VALUE:
            return "Winner"
        return "Potential Winner"
    if cpa_co_lt > 0 and cpa_co_lt <= 20 and purchases_lt == 0:
        if spend_lt >= 50:
            return "Watch List"
        return "Monitor"
    if spend_lt < 50:
        return "Monitor"
    return "Review"


def _safe_float(v):
    try:
        if v is None or v == "":
            return 0.0
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return 0.0
        return f
    except Exception:
        return 0.0


def _budget_to_usd(v):
    """Meta budget fields are usually strings in minor units (cents)."""
    if v is None or v == "":
        return None
    raw = _safe_float(v)
    if raw <= 0:
        return 0.0
    return round(raw / 100.0, 4)


def get_campaign_insights_map(account_id: str, campaign_ids: list, date_preset: str) -> dict:
    if not campaign_ids:
        return {}

    rows = {}
    fields = (
        "campaign_id,campaign_name,spend,cpc,cpm,impressions,clicks,"
        "actions,cost_per_action_type,video_play_actions"
    )

    for group in _chunks(campaign_ids, 50):
        params = {
            "fields": fields,
            "level": "campaign",
            "filtering": json.dumps([
                {
                    "field": "campaign.id",
                    "operator": "IN",
                    "value": group,
                }
            ]),
            "date_preset": date_preset,
            "access_token": ACCESS_TOKEN,
            "limit": 200,
        }
        url = f"{BASE_URL}/{account_id}/insights"
        page_params = dict(params)
        while url:
            data = _request_get(url, page_params, timeout=45)
            for row in data.get("data", []):
                cid = row.get("campaign_id")
                if cid:
                    rows[cid] = row
            url = data.get("paging", {}).get("next")
            page_params = {}
            time.sleep(0.06)

    return rows


def build_campaign_with_metrics(campaign: dict, today_row: dict, lt_row: dict, adset_budget_sum_by_campaign: dict | None = None) -> dict:
    campaign_daily_budget = _budget_to_usd(campaign.get("daily_budget"))
    campaign_lifetime_budget = _budget_to_usd(campaign.get("lifetime_budget"))
    if campaign_daily_budget is None:
        campaign_daily_budget = (adset_budget_sum_by_campaign or {}).get(campaign.get("id"))

    spend_today = _safe_float((today_row or {}).get("spend", 0))
    co_today = _extract_action((today_row or {}).get("actions"), "offsite_conversion.fb_pixel_InitiateCheckout")
    if co_today == 0:
        co_today = _extract_action((today_row or {}).get("actions"), "offsite_conversion.fb_pixel_initiate_checkout")
    cpa_co_today = _extract_cost_per_action((today_row or {}).get("cost_per_action_type"), "offsite_conversion.fb_pixel_InitiateCheckout")
    if cpa_co_today == 0:
        cpa_co_today = _extract_cost_per_action((today_row or {}).get("cost_per_action_type"), "offsite_conversion.fb_pixel_initiate_checkout")
    purchases_today = _extract_action((today_row or {}).get("actions"), "offsite_conversion.fb_pixel_Purchase")
    if purchases_today == 0:
        purchases_today = _extract_action((today_row or {}).get("actions"), "offsite_conversion.fb_pixel_purchase")

    spend_lt = _safe_float((lt_row or {}).get("spend", 0))
    cpc = _safe_float((lt_row or {}).get("cpc", 0))
    cpm = _safe_float((lt_row or {}).get("cpm", 0))
    impressions_lt = int(_safe_float((lt_row or {}).get("impressions", 0)) or 0)
    clicks_lt = int(_safe_float((lt_row or {}).get("clicks", 0)) or 0)

    co_lt = _extract_action((lt_row or {}).get("actions"), "offsite_conversion.fb_pixel_InitiateCheckout")
    if co_lt == 0:
        co_lt = _extract_action((lt_row or {}).get("actions"), "offsite_conversion.fb_pixel_initiate_checkout")
    cpa_co_lt = _extract_cost_per_action((lt_row or {}).get("cost_per_action_type"), "offsite_conversion.fb_pixel_InitiateCheckout")
    if cpa_co_lt == 0:
        cpa_co_lt = _extract_cost_per_action((lt_row or {}).get("cost_per_action_type"), "offsite_conversion.fb_pixel_initiate_checkout")
    purchases_lt = _extract_action((lt_row or {}).get("actions"), "offsite_conversion.fb_pixel_Purchase")
    if purchases_lt == 0:
        purchases_lt = _extract_action((lt_row or {}).get("actions"), "offsite_conversion.fb_pixel_purchase")

    days_live = _calculate_days_live(campaign.get("created_time", ""))
    cost_per_purchase = (spend_lt / purchases_lt) if purchases_lt > 0 else 0.0
    hook_rate = _calculate_hook_rate(lt_row or {})
    has_video = hook_rate is not None

    revenue_lt = purchases_lt * SALE_VALUE
    roi = ((revenue_lt - spend_lt) / spend_lt * 100.0) if spend_lt > 0 else 0.0
    if purchases_lt == 0 and spend_lt > 0:
        roi = -100.0

    verdict = _determine_verdict(days_live, spend_lt, cpc, cpa_co_lt, purchases_lt, cost_per_purchase, has_video)

    return {
        "id": campaign.get("id"),
        "name": campaign.get("name"),
        "status": campaign.get("status") or campaign.get("effective_status"),
        "effective_status": campaign.get("effective_status"),
        "objective": campaign.get("objective"),
        "created_time": campaign.get("created_time"),
        "daily_budget": campaign_daily_budget,
        "lifetime_budget": campaign_lifetime_budget,
        "metrics": {
            "campaign_daily_budget": campaign_daily_budget,
            "campaign_lifetime_budget": campaign_lifetime_budget,
            "days_live": int(days_live),
            "spend_today": round(spend_today, 4),
            "purchases_today": int(purchases_today),
            "checkouts_today": int(co_today),
            "cpa_checkout_today": round(cpa_co_today, 4),
            "spend_lifetime": round(spend_lt, 4),
            "purchases_lifetime": int(purchases_lt),
            "checkouts_lifetime": int(co_lt),
            "cpa_checkout_lifetime": round(cpa_co_lt, 4),
            "cost_per_purchase": round(cost_per_purchase, 4),
            "hook_rate": round(hook_rate, 4) if hook_rate is not None else None,
            "cpc": round(cpc, 4),
            "cpm": round(cpm, 4),
            "impressions": impressions_lt,
            "clicks": clicks_lt,
            "roi": round(roi, 4),
            "verdict": verdict,
        },
    }


def summarize_account_metrics(account_block: dict) -> dict:
    campaigns = account_block.get("campaigns", []) or []
    total_spend_today = sum(_safe_float((c.get("metrics") or {}).get("spend_today", 0)) for c in campaigns)
    total_spend_lt = sum(_safe_float((c.get("metrics") or {}).get("spend_lifetime", 0)) for c in campaigns)
    total_purchases_today = sum(int((c.get("metrics") or {}).get("purchases_today", 0) or 0) for c in campaigns)
    total_purchases_lt = sum(int((c.get("metrics") or {}).get("purchases_lifetime", 0) or 0) for c in campaigns)
    winners = sum(1 for c in campaigns if (c.get("metrics") or {}).get("verdict") in ("Winner", "Potential Winner"))
    kills = sum(1 for c in campaigns if (c.get("metrics") or {}).get("verdict") in ("Kill", "High CPC"))
    return {
        "campaigns": len(campaigns),
        "spend_today": round(total_spend_today, 4),
        "spend_lifetime": round(total_spend_lt, 4),
        "purchases_today": int(total_purchases_today),
        "purchases_lifetime": int(total_purchases_lt),
        "winners": int(winners),
        "kills": int(kills),
    }


def main():
    _log(f"\n{'=' * 60}")
    _log(f"  BM ID: {BM_ID}")
    _log(f"  Insights: {'ON' if WITH_INSIGHTS else 'OFF'}")
    _log(f"{'=' * 60}\n")

    try:
        ad_accounts = get_ad_accounts(BM_ID)
    except RuntimeError as e:
        _log("[ERROR] No se pudieron obtener las cuentas del BM:")
        _log(f"        {e}")
        _log("\nPosibles causas:")
        _log("  1. Token de acceso expirado o invalido")
        _log("  2. Permisos insuficientes (ads_management, business_management)")
        _log("  3. BM ID incorrecto")
        _log("  4. El Business Manager no es accesible con este token")
        sys.exit(1)

    if not ad_accounts:
        _log("[!] No se encontraron cuentas de ads para este BM.")
        sys.exit(0)

    result = []
    total_campaigns = 0

    for idx, account in enumerate(ad_accounts, 1):
        acc_id = account["id"]
        acc_name = account.get("name", "(sin nombre)")
        acc_status = account.get("account_status", "?")
        currency = account.get("currency")
        origen = account.get("_origen", "?")

        _log(f"[{idx}/{len(ad_accounts)}] CUENTA: {acc_name} [{acc_id}] (status: {acc_status}) [{origen}]")

        try:
            campaigns = get_campaigns(acc_id)
        except RuntimeError as e:
            _log(f"  [WARN] No se pudieron traer campanas para {acc_id}: {e}")
            campaigns = []

        campaign_ids = [c.get("id") for c in campaigns if c.get("id")]
        insights_today = {}
        insights_lt = {}
        adset_budget_sum_by_campaign = {}

        if WITH_INSIGHTS and campaign_ids:
            _log(f"  -> {len(campaign_ids)} campanas. Cargando insights (today + lifetime), puede tardar...")
            try:
                insights_today = get_campaign_insights_map(acc_id, campaign_ids, "today")
            except RuntimeError as e:
                _log(f"  [WARN] Fallo insights today en {acc_id}: {e}")
                insights_today = {}
            try:
                insights_lt = get_campaign_insights_map(acc_id, campaign_ids, "maximum")
            except RuntimeError as e:
                _log(f"  [WARN] Fallo insights lifetime en {acc_id}: {e}")
                insights_lt = {}

        if campaign_ids:
            try:
                adset_budget_sum_by_campaign = get_adset_daily_budget_sum_by_campaign(acc_id)
            except RuntimeError as e:
                _log(f"  [WARN] Fallo budget diario por adsets en {acc_id}: {e}")
                adset_budget_sum_by_campaign = {}

        campaigns_out = []
        for camp in campaigns:
            cid = camp.get("id")
            row_today = insights_today.get(cid, {}) if WITH_INSIGHTS else {}
            row_lt = insights_lt.get(cid, {}) if WITH_INSIGHTS else {}
            item = build_campaign_with_metrics(camp, row_today, row_lt, adset_budget_sum_by_campaign)
            campaigns_out.append(item)

        account_out = {
            "account_id": acc_id,
            "account_name": acc_name,
            "status": acc_status,
            "currency": currency,
            "origen": origen,
            "campaigns": campaigns_out,
        }
        if WITH_INSIGHTS:
            account_out["metrics_summary"] = summarize_account_metrics(account_out)

        result.append(account_out)
        total_campaigns += len(campaigns_out)
        _log(f"  -> Campanas cacheadas: {len(campaigns_out)}")
        if WITH_INSIGHTS and account_out.get("metrics_summary"):
            s = account_out["metrics_summary"]
            _log(
                "  -> Summary: spend_today=${:.2f} | spend_lt=${:.2f} | purchases_today={} | purchases_lt={} | winners={} | kills={}".format(
                    s["spend_today"], s["spend_lifetime"], s["purchases_today"], s["purchases_lifetime"], s["winners"], s["kills"]
                )
            )
        _log("")

    _log(f"{'=' * 60}")
    _log(f"  Total cuentas: {len(result)}")
    _log(f"  Total campanas: {total_campaigns}")
    _log(f"{'=' * 60}\n")

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        _log(f"[+] Resultado guardado en: {args.output_json}")

    return result


if __name__ == "__main__":
    main()
