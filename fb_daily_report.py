"""FB Daily Report - ABO Campaign Performance.

Generates a report for all ad accounts discovered from one BM using one token.
Outputs JSON in datatable format for dashboard consumption.

Usage:
  python fb_daily_report.py --access-token TOKEN --bm-id BM_ID
  python fb_daily_report.py --access-token TOKEN --bm-id BM_ID --account THM-113
  python fb_daily_report.py --access-token TOKEN --bm-id BM_ID --csv --print
  python fb_daily_report.py --access-token TOKEN --bm-id BM_ID --output-json logs/explorer.json
"""

import argparse
import io
import requests
import json
import csv
import os
import sys
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ============================================================
# CONFIGURATION
# ============================================================

API_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}/"

SALE_VALUE = 85

# ============================================================
# ACTION TYPE MAPPINGS
# Meta uses DIFFERENT names in 'actions' vs 'cost_per_action_type':
#   actions:              "offsite_conversion.fb_pixel_initiate_checkout"
#   cost_per_action_type: "initiate_checkout"
# We try all variants in priority order — first match wins.
# ============================================================

CHECKOUT_TYPES = [
    "offsite_conversion.fb_pixel_InitiateCheckout",
    "offsite_conversion.fb_pixel_initiate_checkout",
    "initiate_checkout",
    "omni_initiated_checkout",
    "onsite_web_initiate_checkout",
]

PURCHASE_TYPES = [
    "offsite_conversion.fb_pixel_Purchase",
    "offsite_conversion.fb_pixel_purchase",
    "purchase",
    "omni_purchase",
    "onsite_web_purchase",
    "web_in_store_purchase",
]

# ============================================================
# DATATABLE COLUMN DEFINITION
# This is the exact structure the dashboard renders.
# ============================================================

DATATABLE_COLUMNS = [
    {"key": "id",              "label": "Campaign ID",       "type": "text"},
    {"key": "name",            "label": "Campaign Name",     "type": "text"},
    {"key": "status",          "label": "Status",            "type": "badge"},
    {"key": "days",            "label": "Days Live",         "type": "number"},
    {"key": "spend_today",     "label": "Spend Today",       "type": "currency"},
    {"key": "purchases_today", "label": "Purchases Today",   "type": "number"},
    {"key": "co_today",        "label": "CO Today",          "type": "number"},
    {"key": "cpa_co_today",    "label": "CPA CO Today",      "type": "currency"},
    {"key": "spend_lt",        "label": "Spend LT",          "type": "currency"},
    {"key": "purchases_lt",    "label": "Purchases LT",      "type": "number"},
    {"key": "cost_purchase",   "label": "Cost / Purchase",   "type": "currency"},
    {"key": "co_lt",           "label": "CO LT",             "type": "number"},
    {"key": "cpa_co_lt",       "label": "CPA CO LT",         "type": "currency"},
    {"key": "hookrate",        "label": "Hook Rate",         "type": "text"},
    {"key": "cpc",             "label": "CPC",               "type": "currency"},
    {"key": "cpm",             "label": "CPM",               "type": "currency"},
    {"key": "roi",             "label": "ROI",               "type": "percent"},
    {"key": "verdict",         "label": "Verdict",           "type": "badge"},
]

# ============================================================
# API HELPERS
# ============================================================

def api_get(endpoint, token, params=None):
    url = BASE_URL + endpoint
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, params=params or {}, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        print(f"  [API Error] {endpoint}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  [Error] {endpoint}: {e}", file=sys.stderr)
        return None


def paginate_endpoint(endpoint, token, params=None):
    data = api_get(endpoint, token, params)
    if not data or "data" not in data:
        return []
    rows = list(data.get("data", []))
    paging = data.get("paging", {})
    headers = {"Authorization": f"Bearer {token}"}
    while "next" in paging:
        try:
            r = requests.get(paging["next"], headers=headers, timeout=30)
            r.raise_for_status()
            page = r.json()
            rows.extend(page.get("data", []))
            paging = page.get("paging", {})
        except Exception:
            break
    return rows


def get_bm_ad_accounts(bm_id, token):
    common_params = {
        "fields": "id,name,account_status,currency",
        "limit": 200,
    }
    owned = paginate_endpoint(f"{bm_id}/owned_ad_accounts", token, common_params)
    client = paginate_endpoint(f"{bm_id}/client_ad_accounts", token, common_params)

    seen = {}
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


def get_active_campaigns(account_id, token):
    params = {
        "fields": "id,name,status,created_time,effective_status",
        "filtering": json.dumps([{
            "field": "effective_status",
            "operator": "IN",
            "value": ["ACTIVE"]
        }]),
        "limit": 500,
    }
    data = api_get(f"{account_id}/campaigns", token, params)
    if not data or "data" not in data:
        return []
    return data["data"]


def get_campaign_insights(account_id, campaign_ids, token, date_preset):
    if not campaign_ids:
        return {}
    params = {
        "fields": "campaign_id,campaign_name,spend,cpc,cpm,impressions,clicks,"
                  "actions,cost_per_action_type,video_play_actions",
        "level": "campaign",
        "filtering": json.dumps([{
            "field": "campaign.id",
            "operator": "IN",
            "value": campaign_ids
        }]),
        "date_preset": date_preset,
        "limit": 500,
    }
    data = api_get(f"{account_id}/insights", token, params)
    if not data or "data" not in data:
        return {}

    results = {}
    for row in data["data"]:
        results[row["campaign_id"]] = row

    paging = data.get("paging", {})
    while "next" in paging:
        try:
            r = requests.get(paging["next"], timeout=30)
            r.raise_for_status()
            page = r.json()
            for row in page.get("data", []):
                results[row["campaign_id"]] = row
            paging = page.get("paging", {})
        except Exception:
            break

    return results

# ============================================================
# EXTRACTION HELPERS
# ============================================================

def extract_action(actions_list, action_types):
    """Extract action value, trying multiple action_type names in priority order."""
    if not actions_list:
        return 0
    if isinstance(action_types, str):
        action_types = [action_types]
    for atype in action_types:
        for action in actions_list:
            if action.get("action_type") == atype:
                return float(action.get("value", 0))
    return 0


def extract_cost_per_action(cost_list, action_types):
    """Extract cost per action, trying multiple action_type names in priority order."""
    if not cost_list:
        return 0
    if isinstance(action_types, str):
        action_types = [action_types]
    for atype in action_types:
        for item in cost_list:
            if item.get("action_type") == atype:
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
    """Hook Rate = (3s video views / impressions) * 100"""
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
    return round((views_3s / impressions) * 100, 1)

# ============================================================
# VERDICT LOGIC — Matches exactly what Craft Agent produces
# ============================================================

def determine_verdict(days, spend_lt, cpc, cpa_co_lt, co_lt, purchases_lt, cost_per_purchase, has_video):
    # New campaign — don't touch
    if days < 2:
        return "New (<48h)"

    # Not enough data to decide
    if spend_lt < 5:
        return "Insufficient Data"

    # KILL: CPA Checkout > $20 with enough spend
    if cpa_co_lt > 20 and spend_lt >= 20:
        return "Kill"

    # KILL: CPC too high (video threshold $1.50, image threshold $1.00)
    cpc_limit = 1.50 if has_video else 1.00
    if cpc > 0 and cpc > cpc_limit:
        return "High CPC"

    # WINNER: CPA CO <= $20 + has purchases + cost/purchase is profitable
    if cpa_co_lt > 0 and cpa_co_lt <= 20 and purchases_lt > 0:
        if cost_per_purchase <= SALE_VALUE:
            return "Winner"
        else:
            return "Potential Winner"

    # Has good CPA CO but no purchases yet
    if cpa_co_lt > 0 and cpa_co_lt <= 20 and purchases_lt == 0:
        if spend_lt >= 50:
            return "Watch List"
        else:
            return "Monitor"

    # Has purchases but CPA CO is 0 (edge case: cost_per_action missing)
    if purchases_lt > 0 and cpa_co_lt == 0:
        if cost_per_purchase <= SALE_VALUE:
            return "Winner"
        else:
            return "Potential Winner"

    # Has checkouts but no CPA data (fallback calculation)
    if co_lt > 0 and cpa_co_lt == 0 and spend_lt > 0:
        calculated_cpa = spend_lt / co_lt
        if calculated_cpa > 20:
            return "Kill"
        elif purchases_lt > 0 and cost_per_purchase <= SALE_VALUE:
            return "Winner"
        elif purchases_lt > 0:
            return "Potential Winner"
        elif spend_lt >= 50:
            return "Watch List"
        else:
            return "Monitor"

    # Low spend, no checkouts yet
    if spend_lt < 50:
        return "Monitor"

    # High spend, no checkouts, no purchases — bad sign
    if co_lt == 0 and spend_lt >= 50:
        return "Kill"

    return "Review"

# ============================================================
# REPORT GENERATION
# ============================================================

VERDICT_ORDER = {
    "Winner": 0, "Potential Winner": 1, "Watch List": 2,
    "Monitor": 3, "New (<48h)": 4, "Insufficient Data": 5,
    "Review": 6, "High CPC": 7, "Kill": 8,
}


def generate_account_report(account_name, account_id, token):
    print(f"  Fetching {account_name} ({account_id})...", file=sys.stderr)

    campaigns = get_active_campaigns(account_id, token)
    if not campaigns:
        print(f"    No active campaigns.", file=sys.stderr)
        return []

    campaign_ids = [c["id"] for c in campaigns]
    campaign_map = {c["id"]: c for c in campaigns}
    print(f"    {len(campaigns)} active campaigns. Pulling insights...", file=sys.stderr)

    insights_today = get_campaign_insights(account_id, campaign_ids, token, "today")
    insights_lt = get_campaign_insights(account_id, campaign_ids, token, "maximum")

    rows = []
    for cid in campaign_ids:
        camp = campaign_map[cid]
        today = insights_today.get(cid, {})
        lt = insights_lt.get(cid, {})

        days = calculate_days_live(camp.get("created_time", ""))

        # Today
        spend_today = float(today.get("spend", 0))
        co_today = int(extract_action(today.get("actions"), CHECKOUT_TYPES))
        cpa_co_today = extract_cost_per_action(today.get("cost_per_action_type"), CHECKOUT_TYPES)
        purchases_today = int(extract_action(today.get("actions"), PURCHASE_TYPES))

        # Lifetime
        spend_lt = float(lt.get("spend", 0))
        cpc = float(lt.get("cpc", 0))
        cpm = float(lt.get("cpm", 0))
        co_lt = int(extract_action(lt.get("actions"), CHECKOUT_TYPES))
        cpa_co_lt = extract_cost_per_action(lt.get("cost_per_action_type"), CHECKOUT_TYPES)
        purchases_lt = int(extract_action(lt.get("actions"), PURCHASE_TYPES))

        # Calculated
        cost_per_purchase = round(spend_lt / purchases_lt, 2) if purchases_lt > 0 else 0
        hook_rate = calculate_hook_rate(lt)
        has_video = hook_rate is not None

        # ROI
        if purchases_lt > 0 and spend_lt > 0:
            revenue = purchases_lt * SALE_VALUE
            roi = round((revenue - spend_lt) / spend_lt, 3)
        elif spend_lt > 0:
            roi = -1.0
        else:
            roi = 0

        verdict = determine_verdict(
            days, spend_lt, cpc, cpa_co_lt, co_lt,
            purchases_lt, cost_per_purchase, has_video
        )

        rows.append({
            "id": cid,
            "name": camp.get("name", "Unknown"),
            "status": "Active",
            "days": days,
            "spend_today": round(spend_today, 2),
            "purchases_today": purchases_today,
            "co_today": co_today,
            "cpa_co_today": round(cpa_co_today, 2),
            "spend_lt": round(spend_lt, 2),
            "purchases_lt": purchases_lt,
            "cost_purchase": cost_per_purchase,
            "co_lt": co_lt,
            "cpa_co_lt": round(cpa_co_lt, 2),
            "hookrate": f"{hook_rate}%" if hook_rate is not None else "—",
            "cpc": round(cpc, 2),
            "cpm": round(cpm, 2),
            "roi": roi,
            "verdict": verdict,
        })

    rows.sort(key=lambda r: (VERDICT_ORDER.get(r["verdict"], 99), -r["spend_lt"]))
    print(f"    {len(rows)} campaigns processed.", file=sys.stderr)
    return rows


def build_datatable(account_name, account_id, rows):
    """Build a datatable JSON object matching the Craft Agent format."""
    total_spend_today = sum(r["spend_today"] for r in rows)
    total_spend_lt = sum(r["spend_lt"] for r in rows)
    total_purchases_today = sum(r["purchases_today"] for r in rows)
    total_purchases_lt = sum(r["purchases_lt"] for r in rows)
    total_co_today = sum(r["co_today"] for r in rows)
    winners = sum(1 for r in rows if r["verdict"] in ("Winner", "Potential Winner"))
    kills = sum(1 for r in rows if r["verdict"] in ("Kill", "High CPC"))

    date_str = datetime.now().strftime("%B %d, %Y")
    title = f"{account_name} ({account_id}) — Campaign Performance | {date_str}"

    return {
        "title": title,
        "summary": {
            "campaigns": len(rows),
            "spend_today": round(total_spend_today, 2),
            "spend_lt": round(total_spend_lt, 2),
            "purchases_today": total_purchases_today,
            "purchases_lt": total_purchases_lt,
            "checkouts_today": total_co_today,
            "winners": winners,
            "kills": kills,
        },
        "columns": DATATABLE_COLUMNS,
        "rows": rows,
    }


def _parse_hookrate_to_number(value):
    if value in (None, "", "—", "-"):
        return None
    text = str(value).replace("%", "").strip()
    try:
        return round(float(text), 4)
    except Exception:
        return None


def to_explorer_campaign(row):
    roi_pct = -100.0 if row.get("roi") == -1.0 else round(float(row.get("roi", 0)) * 100.0, 4)
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "status": (row.get("status") or "ACTIVE").upper(),
        "effective_status": (row.get("status") or "ACTIVE").upper(),
        "objective": None,
        "created_time": None,
        "daily_budget": None,
        "lifetime_budget": None,
        "metrics": {
            "campaign_daily_budget": None,
            "campaign_lifetime_budget": None,
            "days_live": int(row.get("days", -1)),
            "spend_today": round(float(row.get("spend_today", 0)), 4),
            "purchases_today": int(row.get("purchases_today", 0)),
            "checkouts_today": int(row.get("co_today", 0)),
            "cpa_checkout_today": round(float(row.get("cpa_co_today", 0)), 4),
            "spend_lifetime": round(float(row.get("spend_lt", 0)), 4),
            "purchases_lifetime": int(row.get("purchases_lt", 0)),
            "checkouts_lifetime": int(row.get("co_lt", 0)),
            "cpa_checkout_lifetime": round(float(row.get("cpa_co_lt", 0)), 4),
            "cost_per_purchase": round(float(row.get("cost_purchase", 0)), 4),
            "hook_rate": _parse_hookrate_to_number(row.get("hookrate")),
            "cpc": round(float(row.get("cpc", 0)), 4),
            "cpm": round(float(row.get("cpm", 0)), 4),
            "impressions": 0,
            "clicks": 0,
            "roi": roi_pct,
            "verdict": row.get("verdict", "Review"),
        },
    }


def to_explorer_account(acc, dt):
    rows = dt.get("rows", [])
    return {
        "account_id": acc["account_id"],
        "account_name": acc["account_name"],
        "status": acc.get("account_status", "?"),
        "currency": acc.get("currency"),
        "origen": acc.get("source", "owned"),
        "campaigns": [to_explorer_campaign(r) for r in rows],
    }

# ============================================================
# OUTPUT FORMATTERS
# ============================================================

def print_terminal_table(dt):
    """Print a formatted terminal table from datatable data."""
    s = dt["summary"]
    print(f"\n{'='*140}")
    print(f"  {dt['title']}")
    print(f"  {s['campaigns']} campaigns | Spend Today: ${s['spend_today']:,.2f} | "
          f"Spend LT: ${s['spend_lt']:,.2f} | "
          f"Purchases Today: {s['purchases_today']} | Purchases LT: {s['purchases_lt']} | "
          f"Winners: {s['winners']} | Kills: {s['kills']}")
    print(f"{'='*140}")

    header = (
        f"{'Campaign ID':<20} {'Name':<30} {'Days':>4} "
        f"{'Spend$':>8} {'Purch':>5} {'CO':>3} {'CPA CO':>8} "
        f"{'SpendLT':>10} {'Purch':>5} {'$/Purch':>9} {'CO':>4} {'CPA CO':>8} "
        f"{'Hook%':>6} {'CPC':>6} {'CPM':>7} {'ROI':>8} {'Verdict':<18}"
    )
    print(f"\n{header}")
    print("-" * len(header))

    for r in dt["rows"]:
        name = r["name"][:28] + ".." if len(r["name"]) > 30 else r["name"]
        cpa_t = f"${r['cpa_co_today']:.2f}" if r["cpa_co_today"] > 0 else "—"
        cpp = f"${r['cost_purchase']:.2f}" if r["cost_purchase"] > 0 else "—"
        cpa_l = f"${r['cpa_co_lt']:.2f}" if r["cpa_co_lt"] > 0 else "—"
        roi_val = r["roi"]
        roi_s = f"{roi_val*100:+.1f}%" if roi_val != -1.0 else "-100%"

        print(
            f"{r['id']:<20} {name:<30} {r['days']:>4} "
            f"${r['spend_today']:>7.2f} {r['purchases_today']:>5} {r['co_today']:>3} {cpa_t:>8} "
            f"${r['spend_lt']:>9.2f} {r['purchases_lt']:>5} {cpp:>9} {r['co_lt']:>4} {cpa_l:>8} "
            f"{r['hookrate']:>6} ${r['cpc']:>5.2f} ${r['cpm']:>6.2f} {roi_s:>8} {r['verdict']:<18}"
        )


def export_csv(all_rows, filename):
    if not all_rows:
        return
    fieldnames = [
        "id", "name", "status", "days",
        "spend_today", "purchases_today", "co_today", "cpa_co_today",
        "spend_lt", "purchases_lt", "cost_purchase", "co_lt", "cpa_co_lt",
        "hookrate", "cpc", "cpm", "roi", "verdict"
    ]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"  CSV: {filename}", file=sys.stderr)

# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="FB Daily Report from one BM")
    parser.add_argument("--access-token", required=True, help="Meta access token")
    parser.add_argument("--bm-id", required=True, help="Business Manager ID")
    parser.add_argument("--account", default=None, help="Filter account by name (contains)")
    parser.add_argument("--csv", action="store_true", help="Also export CSV to Downloads")
    parser.add_argument("--print", action="store_true", help="Also print terminal table")
    parser.add_argument("--output-json", default=None, help="Optional explorer-compatible JSON output path")
    args = parser.parse_args()

    do_csv = bool(args.csv)
    do_print = bool(args.print)
    filter_account = args.account.upper() if args.account else None
    token = args.access_token
    bm_id = args.bm_id

    ad_accounts = get_bm_ad_accounts(bm_id, token)
    if not ad_accounts:
        print(json.dumps({"error": f"No ad accounts found for BM {bm_id}"}))
        sys.exit(1)

    all_datatables = []
    all_rows = []

    explorer_accounts = []

    for acc in ad_accounts:
        name = acc["account_name"]
        acct_id = acc["account_id"]
        if filter_account and filter_account not in name.upper():
            continue
        rows = generate_account_report(name, acct_id, token)
        if rows:
            dt = build_datatable(name, acct_id, rows)
            all_datatables.append(dt)
            all_rows.extend(rows)
            explorer_accounts.append(to_explorer_account(acc, dt))
            if do_print:
                print_terminal_table(dt)

    # Global summary
    total_spend_today = sum(r["spend_today"] for r in all_rows)
    total_spend_lt = sum(r["spend_lt"] for r in all_rows)
    total_purchases_today = sum(r["purchases_today"] for r in all_rows)
    total_purchases_lt = sum(r["purchases_lt"] for r in all_rows)
    total_winners = sum(1 for r in all_rows if r["verdict"] in ("Winner", "Potential Winner"))
    total_kills = sum(1 for r in all_rows if r["verdict"] in ("Kill", "High CPC"))

    output = {
        "report_date": datetime.now().strftime("%A, %B %d, %Y at %I:%M %p"),
        "global_summary": {
            "total_campaigns": len(all_rows),
            "spend_today": round(total_spend_today, 2),
            "spend_lt": round(total_spend_lt, 2),
            "purchases_today": total_purchases_today,
            "purchases_lt": total_purchases_lt,
            "winners": total_winners,
            "kills": total_kills,
        },
        "accounts": all_datatables,
    }

    # JSON to stdout (this is what the dashboard reads)
    print(json.dumps(output, indent=2, ensure_ascii=False))

    if args.output_json:
        out_dir = os.path.dirname(args.output_json)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(explorer_accounts, f, ensure_ascii=False, indent=2)
        print(f"  Resultado guardado en: {args.output_json}", file=sys.stderr)

    # Optional CSV export
    if do_csv:
        downloads = os.path.expanduser("~/Downloads")
        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        export_csv(all_rows, os.path.join(downloads, f"fb_report_{date_str}.csv"))

    if do_print:
        print(f"\n{'#'*60}", file=sys.stderr)
        print(f"  GLOBAL SUMMARY", file=sys.stderr)
        print(f"  Campaigns: {len(all_rows)} | Spend Today: ${total_spend_today:,.2f} | "
              f"Spend LT: ${total_spend_lt:,.2f}", file=sys.stderr)
        print(f"  Purchases Today: {total_purchases_today} | Purchases LT: {total_purchases_lt}", file=sys.stderr)
        print(f"  Winners: {total_winners} | Kills: {total_kills}", file=sys.stderr)
        print(f"{'#'*60}", file=sys.stderr)


if __name__ == "__main__":
    main()
