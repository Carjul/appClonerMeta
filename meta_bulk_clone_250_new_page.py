#!/usr/bin/env python3
"""META ADS CLONE v2.1 - FULL RUN (250 ads, new page)
Clone campaign #1 -> create #2..#6 (5 campaigns) x 50 adsets x 1 ad = 250 ads.
Diff vs meta_bulk_clone_fixed.py:
- Uses 250 target ads
- Forces a different Facebook page in creative object_story_spec
"""

import argparse
import concurrent.futures
import copy
import csv
import io
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT, stream=sys.stdout)
logger = logging.getLogger("meta_bulk_clone_250_new_page")


def _log_http_response(tag: str, r: requests.Response, truncate: int = 500):
    logger.debug(
        "HTTP %s | %s %s | status=%d | content-length=%s | x-fb-trace-id=%s | x-fb-rev=%s",
        tag,
        r.request.method,
        r.request.url[:200] if r.request.url else "?",
        r.status_code,
        r.headers.get("Content-Length", "?"),
        r.headers.get("x-fb-trace-id", "n/a"),
        r.headers.get("x-fb-rev", "n/a"),
    )
    body_preview = r.text[:truncate] if r.text else "(empty)"
    logger.debug("HTTP %s | body: %s", tag, body_preview)


def _log_api_error(tag: str, err: dict):
    logger.error(
        "API_ERROR %s | code=%s | subcode=%s | type=%s | fbtrace=%s | message=%s",
        tag,
        err.get("code"),
        err.get("error_subcode", "n/a"),
        err.get("type", "n/a"),
        err.get("fbtrace_id", "n/a"),
        err.get("message", "(no message)"),
    )
    if err.get("error_data"):
        logger.error("API_ERROR %s | error_data=%s", tag, err["error_data"])


_parser = argparse.ArgumentParser(description="META ADS CLONE v2.1 (250 + new page)")
_parser.add_argument("--campaign-id", required=True, help="Original campaign id")
_parser.add_argument("--access-token", required=True, help="Meta Ads access token")
_parser.add_argument("--target-page-id", required=True, help="Target Facebook page id")
_parser.add_argument(
    "--target-instagram-actor-id",
    required=False,
    default=None,
    help="Optional instagram_actor_id for the target page",
)
_args = _parser.parse_args()

ACCESS_TOKEN = _args.access_token
ORIG_CAMPAIGN_ID = _args.campaign_id
TARGET_PAGE_ID = _args.target_page_id
TARGET_IG_ACTOR_ID = _args.target_instagram_actor_id


def obtener_campania(campaign_id: str, access_token: str, api_version: str = "v23.0") -> dict:
    fields = (
        "account_id,name,status,"
        "adsets.limit(100){name,status,daily_budget,lifetime_budget,billing_event,optimization_goal,targeting,promoted_object,bid_strategy},"
        "ads.limit(100){name,status,creative{id},adset_id}"
    )
    url = f"https://graph.facebook.com/{api_version}/{campaign_id}"
    params = {"fields": fields, "access_token": access_token}

    try:
        logger.info("GET campaign %s | url=%s", campaign_id, url)
        r = requests.get(url, params=params, timeout=30)
        _log_http_response(f"GET_CAMPAIGN({campaign_id})", r)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        logger.error("HTTP exception fetching campaign %s: %s", campaign_id, e)
        raise RuntimeError(f"HTTP error fetching campaign: {e}")

    if isinstance(data, dict) and data.get("error"):
        _log_api_error(f"GET_CAMPAIGN({campaign_id})", data["error"])
        raise RuntimeError(f"API error: {data['error'].get('message')}")

    account_raw = data.get("account_id") or data.get("accountId")
    account = str(account_raw) if account_raw is not None else None
    if account and not account.startswith("act_"):
        account = f"act_{account}"

    ads = data.get("ads", {}).get("data", []) if isinstance(data.get("ads"), dict) else []
    first_ad = ads[0] if ads else None

    return {
        "name": data.get("name"),
        "campaign_id": campaign_id,
        "account_id": account,
        "adset_id": first_ad.get("adset_id") if first_ad else None,
        "ad_id": first_ad.get("id") if first_ad else None,
        "creative_id": (first_ad.get("creative") or {}).get("id") if first_ad else None,
    }


def obtener_pagina(page_id: str, access_token: str, api_version: str = "v23.0") -> dict:
    url = f"https://graph.facebook.com/{api_version}/{page_id}"
    params = {"fields": "id,name", "access_token": access_token}
    try:
        logger.info("GET page %s | url=%s", page_id, url)
        r = requests.get(url, params=params, timeout=30)
        _log_http_response(f"GET_PAGE({page_id})", r)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        logger.warning("Could not fetch page %s name: %s", page_id, e)
        return {"id": str(page_id), "name": str(page_id)}

    if isinstance(data, dict) and data.get("error"):
        _log_api_error(f"GET_PAGE({page_id})", data["error"])
        return {"id": str(page_id), "name": str(page_id)}

    return {"id": str(data.get("id", page_id)), "name": str(data.get("name", page_id))}


result = obtener_campania(ORIG_CAMPAIGN_ID, ACCESS_TOKEN)
target_page = obtener_pagina(TARGET_PAGE_ID, ACCESS_TOKEN)

ACCOUNT_ID = result["account_id"]
ORIG_ADSET_ID = result["adset_id"]
ORIG_AD_ID = result["ad_id"]
ORIG_CREATIVE_ID = result["creative_id"]
TARGET_PAGE_NAME = target_page["name"]

N_VALUES = [1, 2, 3, 4, 5]
ADSETS_PER_CAMP = 50

CAMPAIGN_ADSET_LIMIT = 50
ADSET_AD_LIMIT = 1
MULTI_ADVERTISER_ADS = False

SLEEP_BETWEEN = 0.6
TRANSIENT_SLEEP = 3.0
TRANSIENT_RETRIES = 4
SAVE_INTERVAL = 20
MAX_WORKERS = 5

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
STATE_FILE = os.path.join(LOG_DIR, f"meta_clone_250_page_state_{ORIG_CAMPAIGN_ID}.json")
LOG_CSV = os.path.join(LOG_DIR, f"meta_clone_250_page_log_{ORIG_CAMPAIGN_ID}.csv")

API_VER = "v21.0"
BASE_URL = f"https://graph.facebook.com/{API_VER}"

_CAMP_SKIP = {"id", "account_id", "created_time", "updated_time", "buying_type", "name"}
_ADSET_SKIP = {"id", "account_id", "created_time", "updated_time", "campaign_id", "name", "effective_status"}
CAMP_FIELDS = "name,objective,special_ad_categories,status,bid_strategy,lifetime_budget,daily_budget,is_adset_budget_sharing_enabled,start_time,stop_time"
ADSET_FIELDS = (
    "name,campaign_id,daily_budget,lifetime_budget,bid_amount,bid_strategy,"
    "bid_constraints,billing_event,optimization_goal,targeting,status,"
    "start_time,end_time,pacing_type,promoted_object,destination_type,attribution_spec"
)
CR_FIELDS = "object_story_spec,asset_feed_spec,degrees_of_freedom_spec,url_tags"


def _is_rate_limit(err):
    return err.get("code", 0) in (4, 17, 32, 613)


def _is_transient(err):
    if err.get("is_transient"):
        return True
    if err.get("code") == 100 and "Invalid parameter" in err.get("message", ""):
        blame = err.get("error_data", "")
        if not blame or blame == "{}":
            return True
    return False


def api_batch(sub_requests):
    attempt = 0
    urls_summary = [sr.get("relative_url", "?")[:80] for sr in sub_requests]
    logger.info("BATCH request (%d sub-requests): %s", len(sub_requests), urls_summary)
    while True:
        try:
            r = requests.post(
                f"{BASE_URL}/",
                timeout=60,
                data={"access_token": ACCESS_TOKEN, "batch": json.dumps(sub_requests)},
            )
            _log_http_response("BATCH", r)
            results = r.json()
        except Exception as e:
            logger.error("BATCH network exception: %s", e)
            time.sleep(5)
            continue
        if isinstance(results, dict) and "error" in results:
            err = results["error"]
            _log_api_error("BATCH", err)
            if _is_rate_limit(err) or r.status_code >= 500:
                wait = min(2 ** attempt * 3, 120)
                logger.warning("BATCH rate-limit/server-error, retrying in %ds (attempt %d)", wait, attempt)
                time.sleep(wait)
                attempt += 1
                continue
            raise RuntimeError(f"Batch error: {err.get('message')}")
        return [{"code": item.get("code", 0), "body": json.loads(item.get("body", "{}"))} for item in results]


def api_post(endpoint, payload):
    url = f"{BASE_URL}/{endpoint}"
    pl = {**payload, "access_token": ACCESS_TOKEN}
    rl_attempt = tr_attempt = 0
    logger.info("POST %s | payload_keys=%s", endpoint, list(payload.keys()))
    while True:
        try:
            r = requests.post(url, json=pl, timeout=30)
            _log_http_response(f"POST({endpoint})", r)
            d = r.json()
        except Exception as e:
            logger.error("POST %s | network exception: %s", endpoint, e)
            return None, {"message": f"NET_UNKNOWN_RESULT: {e}", "code": -1}
        if "error" not in d:
            return d.get("id"), None
        err = d["error"]
        _log_api_error(f"POST({endpoint})", err)
        if _is_rate_limit(err) or r.status_code >= 500:
            wait = min(2 ** rl_attempt * 2, 120)
            time.sleep(wait)
            rl_attempt += 1
            continue
        if _is_transient(err) and tr_attempt < TRANSIENT_RETRIES:
            tr_attempt += 1
            time.sleep(TRANSIENT_SLEEP)
            continue
        return None, err


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def sk_camp(n):
    return f"n={n}"


def sk_adset(n, i):
    return f"n={n}_i={i}"


console_lock = threading.Lock()


def clog(level, message, n=None, i=None):
    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    nd = f"n={n}" if n is not None else "n=-"
    idd = f"i={i}" if i is not None else "i=-"
    with console_lock:
        print(f"{ts} | {nd} {idd} | {level:<5} | {message}")


def clean_creative_spec(raw):
    afs = copy.deepcopy(raw.get("asset_feed_spec", {}))
    afs["videos"] = [{k: v for k, v in vid.items() if k != "thumbnail_url"} for vid in afs.get("videos", [])]
    afs.pop("shops_bundle", None)
    afs.pop("reasons_to_shop", None)
    dof = copy.deepcopy(raw.get("degrees_of_freedom_spec", {}))
    cfs = dof.get("creative_features_spec", {})
    cfs.pop("standard_enhancements", None)
    result = {
        "object_story_spec": raw.get("object_story_spec", {}),
        "asset_feed_spec": afs,
        "degrees_of_freedom_spec": {"creative_features_spec": cfs} if cfs else {},
    }
    if raw.get("url_tags"):
        result["url_tags"] = raw["url_tags"]
    return result


def patch_object_story_page(raw_spec: dict, target_page_id: str, target_ig_actor_id: str | None):
    spec = copy.deepcopy(raw_spec or {})

    def walk(node):
        if isinstance(node, dict):
            for k, v in list(node.items()):
                if k in ("page_id", "actor_id"):
                    node[k] = str(target_page_id)
                elif k == "instagram_actor_id":
                    if target_ig_actor_id:
                        node[k] = str(target_ig_actor_id)
                    else:
                        node.pop(k, None)
                        continue
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(spec)
    return spec


def clean_adset_payload(adset: dict) -> dict:
    pl = copy.deepcopy(adset)
    if pl.get("destination_type") == "UNDEFINED":
        pl.pop("destination_type")
    if pl.get("lifetime_budget") in ("0", 0):
        pl.pop("lifetime_budget", None)
    targeting = pl.get("targeting", {})
    targeting.pop("age_range", None)
    ig_positions = targeting.get("instagram_positions", [])
    if "explore_home" in ig_positions and "explore" not in ig_positions:
        ig_positions.append("explore")
    promoted = pl.get("promoted_object", {})
    promoted.pop("smart_pse_enabled", None)
    return pl


def fetch_initial_config():
    print("  Initial setup (1 batch call)...", end="", flush=True)
    results = api_batch(
        [
            {"method": "GET", "relative_url": f"{ORIG_CAMPAIGN_ID}?fields={CAMP_FIELDS}"},
            {"method": "GET", "relative_url": f"{ORIG_ADSET_ID}?fields={ADSET_FIELDS}"},
            {"method": "GET", "relative_url": f"{ORIG_AD_ID}?fields=name"},
            {"method": "GET", "relative_url": f"{ORIG_CREATIVE_ID}?fields={CR_FIELDS}"},
        ]
    )
    for idx, label in enumerate(["campaign", "adset", "ad", "creative"]):
        if results[idx]["code"] != 200:
            raise RuntimeError(f"Error reading {label}: {results[idx]['body'].get('error', {}).get('message')}")

    camp_data = results[0]["body"]
    adset_data = results[1]["body"]
    ad_data = results[2]["body"]
    cr_spec = clean_creative_spec(results[3]["body"])
    cr_spec["object_story_spec"] = patch_object_story_page(
        cr_spec.get("object_story_spec", {}),
        TARGET_PAGE_ID,
        TARGET_IG_ACTOR_ID,
    )

    camp_base = {k: v for k, v in camp_data.items() if k not in _CAMP_SKIP and v is not None}
    camp_base["is_adset_budget_sharing_enabled"] = False
    adset_base = clean_adset_payload({k: v for k, v in adset_data.items() if k not in _ADSET_SKIP and v is not None})
    adset_base["status"] = "ACTIVE"

    print(" OK")
    return {
        "orig_camp_name": camp_data["name"],
        "camp_base": camp_base,
        "adset_base": adset_base,
        "adset_name": adset_data["name"],
        "ad_name": ad_data["name"],
        "creative_payload": cr_spec,
        "orig_camp_status": camp_data.get("status", "ACTIVE"),
        "orig_start_time": camp_data.get("start_time"),
        "orig_stop_time": camp_data.get("stop_time"),
    }


def preflight_campaign(camp_id):
    results = api_batch(
        [
            {"method": "GET", "relative_url": f"{camp_id}/adsets?fields=id&limit=200"},
            {"method": "GET", "relative_url": f"{camp_id}/ads?fields=id,adset_id&limit=200"},
        ]
    )
    adset_ids = set()
    adsets_with_ad = set()
    if results[0]["code"] == 200:
        for a in results[0]["body"].get("data", []):
            adset_ids.add(a["id"])
    if results[1]["code"] == 200:
        for a in results[1]["body"].get("data", []):
            adsets_with_ad.add(a.get("adset_id"))
    adsets_with_ad.discard(None)
    return {"adset_ids": adset_ids, "adsets_with_ad": adsets_with_ad}


def ensure_shared_creative(cfg, state):
    if state.get("shared_creative_id"):
        return state["shared_creative_id"]
    creative_id, err = api_post(f"{ACCOUNT_ID}/adcreatives", cfg["creative_payload"])
    if err:
        raise RuntimeError(f"Failed creating creative with new page: {err.get('message', err)}")
    state["shared_creative_id"] = creative_id
    save_state(state)
    return creative_id


def main():
    print("=" * 65)
    print("  META ADS CLONE v2.1 - 250 ads with new page")
    print("=" * 65)
    print(f"  Account       : {ACCOUNT_ID}")
    print(f"  Target page   : {TARGET_PAGE_ID}")
    print(f"  Target IG     : {TARGET_IG_ACTOR_ID or 'none'}")
    print(f"  Guards        : max {CAMPAIGN_ADSET_LIMIT} adsets/campaign | max {ADSET_AD_LIMIT} ad/adset")
    print(f"  Multi-ad      : {'OFF' if not MULTI_ADVERTISER_ADS else 'ON'}")

    cfg = fetch_initial_config()
    state = load_state()
    shared_creative_id = ensure_shared_creative(cfg, state)

    csv_is_new = not os.path.exists(LOG_CSV)
    csvfile = open(LOG_CSV, "a", newline="", encoding="utf-8", buffering=8192)
    writer = csv.DictWriter(
        csvfile,
        fieldnames=["timestamp", "n", "i", "campaign_id", "campaign_name", "adset_id", "creative_id", "ad_id", "status", "note"],
    )
    if csv_is_new:
        writer.writeheader()
        csvfile.flush()

    total_ok = total_fail = total_skip = total_guard = 0
    unsaved_changes = 0

    for n in N_VALUES:
        key_camp = sk_camp(n)
        base_name = cfg["orig_camp_name"].split("#")[0].strip()
        new_name = f"{base_name} - {TARGET_PAGE_NAME} #{n}"

        if state.get(key_camp, {}).get("campaign_id"):
            camp_id = state[key_camp]["campaign_id"]
        else:
            camp_payload = {**cfg["camp_base"], "name": new_name, "status": cfg.get("orig_camp_status", "ACTIVE")}
            if cfg.get("orig_start_time"):
                camp_payload["start_time"] = cfg["orig_start_time"]
            if cfg.get("orig_stop_time"):
                camp_payload["stop_time"] = cfg["orig_stop_time"]
            camp_id, err = api_post(f"{ACCOUNT_ID}/campaigns", camp_payload)
            if err:
                print(f"[FAIL campaign] n={n} -> {err.get('message', '')}")
                continue
            state.setdefault(key_camp, {}).update({"campaign_id": camp_id, "campaign_name": new_name})
            unsaved_changes += 1
            if unsaved_changes >= SAVE_INTERVAL:
                save_state(state)
                unsaved_changes = 0

        pf = preflight_campaign(camp_id)
        existing_adsets = pf["adset_ids"]
        adsets_with_ad = pf["adsets_with_ad"]
        created_this_run = set()
        lock = threading.Lock()

        def process_adset(i):
            nonlocal unsaved_changes, total_ok, total_fail, total_skip, total_guard
            key_as = sk_adset(n, i)
            ts = datetime.now(timezone.utc).isoformat()

            with lock:
                if state.get(key_as, {}).get("ad_id"):
                    total_skip += 1
                    return

            with lock:
                adsets_in_meta_now = len(existing_adsets) + len(created_this_run)
                need_new_adset = not state.get(key_as, {}).get("adset_id")
            if need_new_adset and adsets_in_meta_now >= CAMPAIGN_ADSET_LIMIT:
                with lock:
                    total_guard += 1
                    writer.writerow(
                        {
                            "timestamp": ts,
                            "n": n,
                            "i": i,
                            "campaign_id": camp_id,
                            "campaign_name": new_name,
                            "adset_id": "",
                            "creative_id": "",
                            "ad_id": "",
                            "status": "GUARD_CAMP_LIMIT",
                            "note": f"{adsets_in_meta_now}/{CAMPAIGN_ADSET_LIMIT}",
                        }
                    )
                return

            with lock:
                adset_id = state.get(key_as, {}).get("adset_id")
            if not adset_id:
                adset_id, err = api_post(f"{ACCOUNT_ID}/adsets", {**cfg["adset_base"], "campaign_id": camp_id, "name": cfg["adset_name"]})
                if err:
                    with lock:
                        total_fail += 1
                        writer.writerow(
                            {
                                "timestamp": ts,
                                "n": n,
                                "i": i,
                                "campaign_id": camp_id,
                                "campaign_name": new_name,
                                "adset_id": "",
                                "creative_id": "",
                                "ad_id": "",
                                "status": "ERR_ADSET",
                                "note": err.get("message", "")[:120],
                            }
                        )
                    return
                with lock:
                    state.setdefault(key_as, {})["adset_id"] = adset_id
                    created_this_run.add(adset_id)
                    unsaved_changes += 1
                    if unsaved_changes >= SAVE_INTERVAL:
                        save_state(state)
                        unsaved_changes = 0
                time.sleep(SLEEP_BETWEEN)

            with lock:
                if adset_id in adsets_with_ad:
                    total_guard += 1
                    writer.writerow(
                        {
                            "timestamp": ts,
                            "n": n,
                            "i": i,
                            "campaign_id": camp_id,
                            "campaign_name": new_name,
                            "adset_id": adset_id,
                            "creative_id": "",
                            "ad_id": "",
                            "status": "GUARD_ADSET_HAS_AD",
                            "note": "preflight",
                        }
                    )
                    return

            ad_id, err = api_post(
                f"{ACCOUNT_ID}/ads",
                {
                    "name": cfg["ad_name"],
                    "adset_id": adset_id,
                    "creative": {"creative_id": shared_creative_id},
                    "status": "ACTIVE",
                },
            )
            if err:
                with lock:
                    total_fail += 1
                    writer.writerow(
                        {
                            "timestamp": ts,
                            "n": n,
                            "i": i,
                            "campaign_id": camp_id,
                            "campaign_name": new_name,
                            "adset_id": adset_id,
                            "creative_id": shared_creative_id,
                            "ad_id": "",
                            "status": "ERR_AD",
                            "note": err.get("message", "")[:120],
                        }
                    )
                return

            with lock:
                state.setdefault(key_as, {})["creative_id"] = shared_creative_id
                state.setdefault(key_as, {})["ad_id"] = ad_id
                adsets_with_ad.add(adset_id)
                total_ok += 1
                save_state(state)
                unsaved_changes = 0
                writer.writerow(
                    {
                        "timestamp": ts,
                        "n": n,
                        "i": i,
                        "campaign_id": camp_id,
                        "campaign_name": new_name,
                        "adset_id": adset_id,
                        "creative_id": shared_creative_id,
                        "ad_id": ad_id,
                        "status": "OK",
                        "note": "",
                    }
                )
            time.sleep(SLEEP_BETWEEN)

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = [ex.submit(process_adset, i) for i in range(1, ADSETS_PER_CAMP + 1)]
            for f in concurrent.futures.as_completed(futures):
                try:
                    f.result()
                except Exception as e:
                    clog("ERROR", f"thread exception: {e}", n=n)

    csvfile.close()
    if unsaved_changes > 0:
        save_state(state)

    logger.info("=" * 65)
    logger.info("Done")
    logger.info("OK=%d | Skip=%d | Guards=%d | Fail=%d", total_ok, total_skip, total_guard, total_fail)
    logger.info("Shared creative with new page: %s", state.get("shared_creative_id", "?"))
    logger.info("State: %s", STATE_FILE)
    logger.info("CSV:   %s", LOG_CSV)


if __name__ == "__main__":
    main()
