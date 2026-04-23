#!/usr/bin/env python3
"""FB Daily Report - ABO Campaign Performance

Run report for all ad accounts discovered from one Business Manager.

Usage:
  python fb_daily_report.py --access-token <TOKEN> --bm-id <BM_ID>
  python fb_daily_report.py --access-token <TOKEN> --bm-id <BM_ID> --account THM-113
  python fb_daily_report.py --access-token <TOKEN> --bm-id <BM_ID> --json logs/report.json
"""

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any

import requests


API_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}/"
SALE_VALUE = 85.0


class RunLogger:
    def __init__(self):
        self.lines = []

    def log(self, message: str):
        print(message)
        self.lines.append(message)


def api_get(endpoint, token, params=None):
    url = BASE_URL + endpoint
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, params=params or {}, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        return {"_error": f"[API Error] {endpoint}: {e}"}
    except Exception as e:
        return {"_error": f"[Error] {endpoint}: {e}"}


def paginate(endpoint, token, params=None):
    data = api_get(endpoint, token, params)
    if not isinstance(data, dict) or "_error" in data:
        return [], (data or {}).get("_error")

    rows = list(data.get("data", []))
    paging = data.get("paging", {})
    while isinstance(paging, dict) and "next" in paging:
        try:
            r = requests.get(paging["next"], timeout=30)
            r.raise_for_status()
            page = r.json()
            if isinstance(page, dict):
                rows.extend(page.get("data", []))
                paging = page.get("paging", {})
            else:
                break
        except Exception as e:
            return rows, f"[Pagination Error] {endpoint}: {e}"

    return rows, None


def get_bm_ad_accounts(bm_id, token):
    common = {
        "fields": "id,name,account_status,currency",
        "limit": 500,
    }

    owned, err_owned = paginate(f"{bm_id}/owned_ad_accounts", token, common)
    client, err_client = paginate(f"{bm_id}/client_ad_accounts", token, common)

    seen = {}
    for acc in owned:
        if not isinstance(acc, dict):
            continue
        seen[str(acc.get("id"))] = {
            "name": acc.get("name", "UNKNOWN"),
            "account_id": str(acc.get("id")),
            "currency": acc.get("currency", ""),
            "source": "owned",
        }
    for acc in client:
        if not isinstance(acc, dict):
            continue
        aid = str(acc.get("id"))
        if aid not in seen:
            seen[aid] = {
                "name": acc.get("name", "UNKNOWN"),
                "account_id": aid,
                "currency": acc.get("currency", ""),
                "source": "client",
            }

    errs = [e for e in (err_owned, err_client) if e]
    return list(seen.values()), errs


def get_active_campaigns(account_id, token):
    params = {
        "fields": "id,name,status,created_time,effective_status",
        "filtering": json.dumps(
            [
                {
                    "field": "effective_status",
                    "operator": "IN",
                    "value": ["ACTIVE"],
                }
            ]
        ),
        "limit": 500,
    }
    rows, err = paginate(f"{account_id}/campaigns", token, params)
    return rows, err


def get_campaign_insights(account_id, campaign_ids, token, date_preset):
    if not campaign_ids:
        return {}, None

    params = {
        "fields": "campaign_id,campaign_name,spend,cpc,cpm,impressions,clicks,actions,cost_per_action_type,video_play_actions",
        "level": "campaign",
        "filtering": json.dumps(
            [
                {
                    "field": "campaign.id",
                    "operator": "IN",
                    "value": campaign_ids,
                }
            ]
        ),
        "date_preset": date_preset,
        "limit": 500,
    }
    rows, err = paginate(f"{account_id}/insights", token, params)
    out = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = row.get("campaign_id")
        if cid:
            out[cid] = row
    return out, err


def extract_action(actions_list, action_type):
    if not actions_list:
        return 0
    for action in actions_list:
        if action.get("action_type") == action_type:
            return float(action.get("value", 0))
    return 0


def extract_cost_per_action(cost_list, action_type):
    if not cost_list:
        return 0
    for item in cost_list:
        if item.get("action_type") == action_type:
            return float(item.get("value", 0))
    return 0


def calculate_days_live(created_time_str):
    try:
        created = datetime.fromisoformat(created_time_str.replace("+0000", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - created).days
    except Exception:
        return -1


def calculate_hook_rate(insights):
    video_plays = insights.get("video_play_actions", [])
    impressions = float(insights.get("impressions", 0))
    if not video_plays or impressions == 0:
        return None

    views_3s = 0
    for vp in video_plays:
        if vp.get("action_type") == "video_view":
            views_3s = float(vp.get("value", 0))
            break

    if views_3s == 0:
        return None
    return (views_3s / impressions) * 100


def determine_verdict(days, spend_lt, cpc, cpm, cpa_co_lt, purchases_lt, cost_per_purchase, has_video):
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


def fmt_currency(val):
    if val == 0:
        return "$0.00"
    return f"${val:,.2f}"


def generate_account_report(account_name, account_id, token, logger):
    logger.log(f"\n  Fetching {account_name} ({account_id})...")

    campaigns, err = get_active_campaigns(account_id, token)
    if err:
        logger.log(f"    {err}")
    if not campaigns:
        logger.log("    No active campaigns found.")
        return []

    campaign_ids = [str(c.get("id")) for c in campaigns if isinstance(c, dict) and c.get("id")]
    campaign_map = {str(c.get("id")): c for c in campaigns if isinstance(c, dict) and c.get("id")}
    logger.log(f"    Found {len(campaigns)} active campaigns. Pulling insights...")

    insights_today, err_today = get_campaign_insights(account_id, campaign_ids, token, "today")
    insights_lt, err_lt = get_campaign_insights(account_id, campaign_ids, token, "maximum")
    if err_today:
        logger.log(f"    {err_today}")
    if err_lt:
        logger.log(f"    {err_lt}")

    rows = []
    for cid in campaign_ids:
        camp = campaign_map[cid]
        today = insights_today.get(cid, {})
        lt = insights_lt.get(cid, {})

        days = calculate_days_live(camp.get("created_time", ""))

        spend_today = float(today.get("spend", 0))
        co_today = extract_action(today.get("actions"), "offsite_conversion.fb_pixel_InitiateCheckout")
        if co_today == 0:
            co_today = extract_action(today.get("actions"), "offsite_conversion.fb_pixel_initiate_checkout")
        cpa_co_today = extract_cost_per_action(today.get("cost_per_action_type"), "offsite_conversion.fb_pixel_InitiateCheckout")
        if cpa_co_today == 0:
            cpa_co_today = extract_cost_per_action(today.get("cost_per_action_type"), "offsite_conversion.fb_pixel_initiate_checkout")
        purchases_today = extract_action(today.get("actions"), "offsite_conversion.fb_pixel_Purchase")
        if purchases_today == 0:
            purchases_today = extract_action(today.get("actions"), "offsite_conversion.fb_pixel_purchase")

        spend_lt = float(lt.get("spend", 0))
        cpc = float(lt.get("cpc", 0))
        cpm = float(lt.get("cpm", 0))
        co_lt = extract_action(lt.get("actions"), "offsite_conversion.fb_pixel_InitiateCheckout")
        if co_lt == 0:
            co_lt = extract_action(lt.get("actions"), "offsite_conversion.fb_pixel_initiate_checkout")
        cpa_co_lt = extract_cost_per_action(lt.get("cost_per_action_type"), "offsite_conversion.fb_pixel_InitiateCheckout")
        if cpa_co_lt == 0:
            cpa_co_lt = extract_cost_per_action(lt.get("cost_per_action_type"), "offsite_conversion.fb_pixel_initiate_checkout")
        purchases_lt = extract_action(lt.get("actions"), "offsite_conversion.fb_pixel_Purchase")
        if purchases_lt == 0:
            purchases_lt = extract_action(lt.get("actions"), "offsite_conversion.fb_pixel_purchase")

        cost_per_purchase = (spend_lt / purchases_lt) if purchases_lt > 0 else 0
        hook_rate = calculate_hook_rate(lt)
        has_video = hook_rate is not None

        revenue_lt = purchases_lt * SALE_VALUE
        roi = ((revenue_lt - spend_lt) / spend_lt * 100) if spend_lt > 0 else 0
        if purchases_lt == 0 and spend_lt > 0:
            roi = -100.0

        verdict = determine_verdict(
            days, spend_lt, cpc, cpm, cpa_co_lt, purchases_lt, cost_per_purchase, has_video
        )

        rows.append(
            {
                "account": account_name,
                "campaign_id": cid,
                "campaign_name": camp.get("name", "Unknown"),
                "status": camp.get("effective_status", "ACTIVE"),
                "days_live": days,
                "spend_today": spend_today,
                "purchases_today": int(purchases_today),
                "co_today": int(co_today),
                "cpa_co_today": cpa_co_today,
                "spend_lt": spend_lt,
                "purchases_lt": int(purchases_lt),
                "cost_per_purchase": cost_per_purchase,
                "co_lt": int(co_lt),
                "cpa_co_lt": cpa_co_lt,
                "hook_rate": hook_rate,
                "cpc": cpc,
                "cpm": cpm,
                "roi": roi,
                "verdict": verdict,
            }
        )

    verdict_order = {
        "Winner": 0,
        "Potential Winner": 1,
        "Watch List": 2,
        "Monitor": 3,
        "Review": 4,
        "New (<48h)": 5,
        "Insufficient Data": 6,
        "High CPC": 7,
        "Kill": 8,
    }
    rows.sort(key=lambda r: (verdict_order.get(r["verdict"], 99), -r["spend_lt"]))

    logger.log(f"    {len(rows)} campaigns processed.")
    return rows


def print_account_table(account_name, rows, logger):
    if not rows:
        return

    total_spend_today = sum(r["spend_today"] for r in rows)
    total_spend_lt = sum(r["spend_lt"] for r in rows)
    total_purchases_today = sum(r["purchases_today"] for r in rows)
    total_purchases_lt = sum(r["purchases_lt"] for r in rows)
    total_co_lt = sum(r["co_lt"] for r in rows)
    winners = sum(1 for r in rows if r["verdict"] in ("Winner", "Potential Winner"))
    kills = sum(1 for r in rows if r["verdict"] in ("Kill", "High CPC"))

    logger.log(f"\n{'=' * 120}")
    logger.log(f"  {account_name} - Campaign Performance | {datetime.now().strftime('%B %d, %Y')}")
    logger.log(
        f"  {len(rows)} active campaigns | Spend Today: {fmt_currency(total_spend_today)} | "
        f"Spend LT: {fmt_currency(total_spend_lt)} | "
        f"Purchases Today: {total_purchases_today} | Purchases LT: {total_purchases_lt} | "
        f"Checkouts LT: {total_co_lt} | Winners: {winners} | Kills: {kills}"
    )
    logger.log(f"{'=' * 120}")

    header = (
        f"{'Campaign ID':<20} {'Campaign Name':<30} {'Status':<8} {'Days':>4} "
        f"{'Spend $':>9} {'Purch':>5} {'CO':>4} {'CPA CO':>8} "
        f"{'Spend LT':>10} {'Purch':>5} {'$/Purch':>9} {'CO LT':>5} {'CPA CO':>8} "
        f"{'Hook%':>6} {'CPC':>6} {'CPM':>7} {'ROI':>8} {'Verdict':<18}"
    )
    logger.log(f"\n{header}")
    logger.log("-" * len(header))

    for r in rows:
        hook_str = f"{r['hook_rate']:.1f}%" if r["hook_rate"] is not None else "-"
        roi_str = f"{r['roi']:+.1f}%" if r["roi"] != -100 else "-100%"
        cpa_today_str = fmt_currency(r["cpa_co_today"]) if r["cpa_co_today"] > 0 else "-"
        cpp_str = fmt_currency(r["cost_per_purchase"]) if r["cost_per_purchase"] > 0 else "-"
        cpa_lt_str = fmt_currency(r["cpa_co_lt"]) if r["cpa_co_lt"] > 0 else "-"

        name_short = r["campaign_name"][:28] + ".." if len(r["campaign_name"]) > 30 else r["campaign_name"]

        logger.log(
            f"{r['campaign_id']:<20} {name_short:<30} {'Active':<8} {r['days_live']:>4} "
            f"{fmt_currency(r['spend_today']):>9} {r['purchases_today']:>5} {r['co_today']:>4} {cpa_today_str:>8} "
            f"{fmt_currency(r['spend_lt']):>10} {r['purchases_lt']:>5} {cpp_str:>9} {r['co_lt']:>5} {cpa_lt_str:>8} "
            f"{hook_str:>6} {fmt_currency(r['cpc']):>6} {fmt_currency(r['cpm']):>7} {roi_str:>8} {r['verdict']:<18}"
        )


def save_json(path, payload):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="FB Daily Report using one token and one BM")
    parser.add_argument("--access-token", required=True, help="Meta token")
    parser.add_argument("--bm-id", required=True, help="Business Manager ID")
    parser.add_argument("--account", default=None, help="Filter account by name (contains)")
    parser.add_argument("--json", default=None, help="Output JSON path (includes rows + logs)")
    parser.add_argument("--sale-value", type=float, default=85.0, help="Average sale value for ROI")
    args = parser.parse_args()

    global SALE_VALUE
    if args.sale_value > 0:
        SALE_VALUE = args.sale_value

    logger = RunLogger()

    logger.log(f"\n{'#' * 60}")
    logger.log("  FB DAILY REPORT - ABO Campaign Performance")
    logger.log(f"  {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}")
    logger.log(f"  BM ID: {args.bm_id}")
    logger.log(f"{'#' * 60}")

    accounts, bm_errors = get_bm_ad_accounts(args.bm_id, args.access_token)
    for e in bm_errors:
        logger.log(f"  {e}")

    if not accounts:
        logger.log("\n[ERROR] No ad accounts found for this BM.")
        raise SystemExit(1)

    filter_account = args.account.upper() if args.account else None
    all_rows = []

    for acc in accounts:
        if not isinstance(acc, dict):
            continue
        name = acc["name"]
        account_id = acc["account_id"]
        if not account_id.startswith("act_"):
            account_id = f"act_{account_id}"
        if filter_account and filter_account not in name.upper():
            continue

        rows = generate_account_report(name, account_id, args.access_token, logger)
        if rows:
            print_account_table(name, rows, logger)
            all_rows.extend(rows)

    if all_rows:
        total_spend = sum(r["spend_today"] for r in all_rows)
        total_spend_lt = sum(r["spend_lt"] for r in all_rows)
        total_purchases = sum(r["purchases_today"] for r in all_rows)
        total_purchases_lt = sum(r["purchases_lt"] for r in all_rows)
        total_winners = sum(1 for r in all_rows if r["verdict"] in ("Winner", "Potential Winner"))
        total_kills = sum(1 for r in all_rows if r["verdict"] in ("Kill", "High CPC"))

        logger.log(f"\n{'#' * 60}")
        logger.log("  GLOBAL SUMMARY")
        logger.log(f"{'#' * 60}")
        logger.log(f"  Total Campaigns:    {len(all_rows)}")
        logger.log(f"  Spend Today:        {fmt_currency(total_spend)}")
        logger.log(f"  Spend Lifetime:     {fmt_currency(total_spend_lt)}")
        logger.log(f"  Purchases Today:    {total_purchases}")
        logger.log(f"  Purchases Lifetime: {total_purchases_lt}")
        logger.log(f"  Winners:            {total_winners}")
        logger.log(f"  To Kill:            {total_kills}")
        logger.log(f"{'#' * 60}")

    if args.json:
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "bm_id": args.bm_id,
            "rows": all_rows,
            "logs": logger.lines,
            "accounts_discovered": len(accounts),
            "campaigns_reported": len(all_rows),
        }
        save_json(args.json, payload)
        logger.log(f"\n  JSON saved to: {args.json}")
    else:
        logger.log("\n  Tip: pass --json <path> to save rows + logs.")


if __name__ == "__main__":
    main()
