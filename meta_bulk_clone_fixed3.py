#!/usr/bin/env python3
"""META ADS CLONE v2.0 — FULL RUN — Hannah Brooks / V1_Agres_ video2
Clonar campaña 120241270492130475 → crear #2..#5 (4 campañas) × 50 adsets × 1 ad = 200 ads
"""

import argparse, copy, csv, io, json, logging, os, sys, time
import concurrent.futures, threading
from datetime import datetime, timezone
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Logging setup ─────────────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT, stream=sys.stdout)
logger = logging.getLogger("meta_bulk_clone")


def _log_http_response(tag: str, r: requests.Response, truncate: int = 500):
    """Log completo de una respuesta HTTP de la API de Meta."""
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
    """Log detallado de un error de la API de Meta."""
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
    if err.get("error_user_title") or err.get("error_user_msg"):
        logger.error(
            "API_ERROR %s | user_title=%s | user_msg=%s",
            tag,
            err.get("error_user_title", ""),
            err.get("error_user_msg", ""),
        )

# ── CONFIG TEST ───────────────────────────────────────────────────────────────
_parser = argparse.ArgumentParser(description="META ADS CLONE v2.0")
_parser.add_argument("--campaign-id", required=True, help="ID de la campaña original a clonar")
_parser.add_argument("--access-token", required=True, help="Access token de Meta Ads")
_args = _parser.parse_args()

ACCESS_TOKEN     = _args.access_token
ORIG_CAMPAIGN_ID = _args.campaign_id

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
        "raw": data,
    }

result =obtener_campania(ORIG_CAMPAIGN_ID, ACCESS_TOKEN)

ACCOUNT_ID       = result["account_id"]

ORIG_ADSET_ID    = result["adset_id"]
ORIG_AD_ID       = result["ad_id"]
ORIG_CREATIVE_ID = result["creative_id"]

NAME_SUFFIX_ORIG  = "#1"
N_VALUES          = [2, 3, 4, 5]   # campañas #2–#5
ADSETS_PER_CAMP   = 50             # 50 adsets por campaña

CAMPAIGN_ADSET_LIMIT = 50
ADSET_AD_LIMIT       = 1
MULTI_ADVERTISER_ADS = False   # False = OPT_OUT, True = OPT_IN (desde ago 2024 es OPT_IN por defecto)

SLEEP_BETWEEN     = 0.6
TRANSIENT_SLEEP   = 3.0
TRANSIENT_RETRIES = 4
SAVE_INTERVAL     = 20  # checkpoint de estado cada N cambios (reduce I/O)
MAX_WORKERS       = 5   # número de hilos para paralelismo (ajustable)

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
STATE_FILE = os.path.join(LOG_DIR, "meta_clone_state_"+ORIG_CAMPAIGN_ID+".json")
LOG_CSV    = os.path.join(LOG_DIR, "meta_clone_log_"+ORIG_CAMPAIGN_ID+".csv")

API_VER  = "v21.0"
BASE_URL = f"https://graph.facebook.com/{API_VER}"

_CAMP_SKIP  = {"id","account_id","created_time","updated_time","buying_type","name"}
_ADSET_SKIP = {"id","account_id","created_time","updated_time","campaign_id","name","effective_status"}
CAMP_FIELDS  = "name,objective,special_ad_categories,status,bid_strategy,lifetime_budget,daily_budget,is_adset_budget_sharing_enabled,start_time,stop_time"
ADSET_FIELDS = ("name,campaign_id,daily_budget,lifetime_budget,bid_amount,bid_strategy,"
               "bid_constraints,billing_event,optimization_goal,targeting,status,"
               "start_time,end_time,pacing_type,promoted_object,destination_type,attribution_spec")
CR_FIELDS    = "object_story_spec,asset_feed_spec,degrees_of_freedom_spec,url_tags"

# ── API HELPERS ───────────────────────────────────────────────────────────────
def _is_rate_limit(err): return err.get("code", 0) in (4, 17, 32, 613)

def _is_transient(err):
    if err.get("is_transient"): return True
    if err.get("code") == 100 and "Invalid parameter" in err.get("message", ""):
        blame = err.get("error_data", "")
        if not blame or blame == "{}": return True
    return False

def api_batch(sub_requests):
    attempt = 0
    urls_summary = [sr.get("relative_url", "?")[:80] for sr in sub_requests]
    logger.info("BATCH request (%d sub-requests): %s", len(sub_requests), urls_summary)
    while True:
        try:
            r = requests.post(f"{BASE_URL}/", timeout=60,
                data={"access_token": ACCESS_TOKEN, "batch": json.dumps(sub_requests)})
            _log_http_response("BATCH", r)
            results = r.json()
        except Exception as e:
            logger.error("BATCH network exception: %s", e)
            time.sleep(5); continue
        if isinstance(results, dict) and "error" in results:
            err = results["error"]
            _log_api_error("BATCH", err)
            if _is_rate_limit(err) or r.status_code >= 500:
                wait = min(2**attempt*3, 120)
                logger.warning("BATCH rate-limit/server-error, retrying in %ds (attempt %d)", wait, attempt)
                time.sleep(wait); attempt += 1; continue
            raise RuntimeError(f"Batch error: {err.get('message')}")
        # Log cada sub-respuesta del batch
        for idx, item in enumerate(results):
            code = item.get("code", 0)
            body = json.loads(item.get("body", "{}"))
            if code != 200:
                logger.warning(
                    "BATCH sub[%d] HTTP %d | url=%s | error=%s",
                    idx, code, urls_summary[idx] if idx < len(urls_summary) else "?",
                    json.dumps(body.get("error", {}), ensure_ascii=False)[:300],
                )
            else:
                logger.debug("BATCH sub[%d] HTTP 200 OK | url=%s", idx, urls_summary[idx] if idx < len(urls_summary) else "?")
        return [{"code": item.get("code", 0),
                 "body": json.loads(item.get("body", "{}"))} for item in results]

def api_post(endpoint, payload):
    url = f"{BASE_URL}/{endpoint}"
    pl  = {**payload, "access_token": ACCESS_TOKEN}
    rl_attempt = tr_attempt = 0
    # Log del payload sin access_token
    logger.info("POST %s | payload_keys=%s", endpoint, list(payload.keys()))
    logger.debug("POST %s | payload=%s", endpoint, json.dumps(payload, ensure_ascii=False, default=str)[:600])
    while True:
        try:
            r = requests.post(url, json=pl, timeout=30)
            _log_http_response(f"POST({endpoint})", r)
            d = r.json()
        except Exception as e:
            logger.error("POST %s | network exception: %s", endpoint, e)
            return None, {"message": f"NET_UNKNOWN_RESULT: {e}", "code": -1}
        if "error" not in d:
            created_id = d.get("id")
            logger.info("POST %s | SUCCESS id=%s", endpoint, created_id)
            return created_id, None
        err = d["error"]
        _log_api_error(f"POST({endpoint})", err)
        if _is_rate_limit(err) or r.status_code >= 500:
            wait = min(2**rl_attempt*2, 120)
            logger.warning("POST %s | rate-limit/5xx, retry in %ds (rl_attempt=%d)", endpoint, wait, rl_attempt)
            time.sleep(wait); rl_attempt += 1; continue
        if _is_transient(err) and tr_attempt < TRANSIENT_RETRIES:
            tr_attempt += 1
            logger.warning("POST %s | transient error, retry %d/%d", endpoint, tr_attempt, TRANSIENT_RETRIES)
            time.sleep(TRANSIENT_SLEEP); continue
        logger.error("POST %s | FATAL error, no more retries", endpoint)
        return None, err


def find_existing_ad_in_adset(adset_id):
    logger.info("RECOVER checking existing ads in adset %s", adset_id)
    results = api_batch([
        {"method":"GET","relative_url":f"{adset_id}/ads?fields=id&limit=2"},
    ])
    if results[0]["code"] != 200:
        logger.warning("RECOVER adset %s lookup failed: HTTP %d", adset_id, results[0]["code"])
        return None
    data = results[0]["body"].get("data", [])
    found = data[0].get("id") if data else None
    logger.info("RECOVER adset %s | found_ad=%s", adset_id, found)
    return found

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f: return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def sk_camp(n):     return f"n={n}"
def sk_adset(n, i): return f"n={n}_i={i}"

# Console logging helper (thread-safe, compact)
console_lock = threading.Lock()
def clog(level, message, n=None, i=None):
    ts = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
    nd = f"n={n}" if n is not None else "n=-"
    idd = f"i={i}" if i is not None else "i=-"
    with console_lock:
        print(f"{ts} | {nd} {idd} | {level:<5} | {message}")

def clean_creative_spec(raw):
    afs = copy.deepcopy(raw.get("asset_feed_spec", {}))
    afs["videos"] = [{k:v for k,v in vid.items() if k!="thumbnail_url"} for vid in afs.get("videos",[])]
    afs.pop("shops_bundle", None); afs.pop("reasons_to_shop", None)
    dof = copy.deepcopy(raw.get("degrees_of_freedom_spec", {}))
    cfs = dof.get("creative_features_spec", {})
    cfs.pop("standard_enhancements", None)
    result = {
        "object_story_spec":       raw.get("object_story_spec", {}),
        "asset_feed_spec":         afs,
        "degrees_of_freedom_spec": {"creative_features_spec": cfs} if cfs else {},
    }
    if raw.get("url_tags"):
        result["url_tags"] = raw["url_tags"]
    return result

def clean_adset_payload(adset: dict) -> dict:
    """
    Elimina campos del adset original que no se pueden copiar directamente:
      - destination_type=UNDEFINED : Meta rechaza este valor
      - lifetime_budget=0 : incompatible con daily_budget
      - targeting.age_range : campo derivado (read-only)
      - targeting.locales si genera conflicto
      - promoted_object.smart_pse_enabled : campo de solo lectura
    PRESERVAR:
      - start_time / end_time : para mantener la programación original
    """
    import copy
    pl = copy.deepcopy(adset)

    # PRESERVAR start_time y end_time para mantener programación original
    # pl.pop("start_time", None)
    # pl.pop("end_time", None)

    # destination_type UNDEFINED → Meta falla con ese valor
    if pl.get("destination_type") == "UNDEFINED":
        pl.pop("destination_type")

    # lifetime_budget=0 es inconsistente con daily_budget
    if pl.get("lifetime_budget") in ("0", 0):
        pl.pop("lifetime_budget", None)

    # age_range es derivado de age_min/age_max, no editable
    targeting = pl.get("targeting", {})
    targeting.pop("age_range", None)

    # FIX: Meta exige que si se usa "explore_home" tambien este "explore"
    ig_positions = targeting.get("instagram_positions", [])
    if "explore_home" in ig_positions and "explore" not in ig_positions:
        ig_positions.append("explore")
        logger.info("AUTO-FIX: added 'explore' to instagram_positions (required by explore_home)")

    # smart_pse_enabled es read-only dentro de promoted_object
    promoted = pl.get("promoted_object", {})
    promoted.pop("smart_pse_enabled", None)

    return pl


# ── FETCH INITIAL (1 batch call) ──────────────────────────────────────────────
def fetch_initial_config():
    print("  Setup inicial (1 batch call)...", end="", flush=True)
    results = api_batch([
        {"method":"GET","relative_url":f"{ORIG_CAMPAIGN_ID}?fields={CAMP_FIELDS}"},
        {"method":"GET","relative_url":f"{ORIG_ADSET_ID}?fields={ADSET_FIELDS}"},
        {"method":"GET","relative_url":f"{ORIG_AD_ID}?fields=name"},
        {"method":"GET","relative_url":f"{ORIG_CREATIVE_ID}?fields={CR_FIELDS}"},
    ])
    for idx, label in enumerate(["campaign","adset","ad","creative"]):
        if results[idx]["code"] != 200:
            raise RuntimeError(f"Error leyendo {label}: {results[idx]['body'].get('error',{}).get('message')}")
    camp_data  = results[0]["body"]
    adset_data = results[1]["body"]
    ad_data    = results[2]["body"]
    cr_spec    = clean_creative_spec(results[3]["body"])

    # Capturar estado y programación original de la campaña
    orig_camp_status = camp_data.get("status", "ACTIVE")
    orig_start_time = camp_data.get("start_time")
    orig_stop_time = camp_data.get("stop_time")

    camp_base  = {k:v for k,v in camp_data.items() if k not in _CAMP_SKIP and v is not None}
    camp_base["is_adset_budget_sharing_enabled"] = False
    adset_base = clean_adset_payload({k:v for k,v in adset_data.items() if k not in _ADSET_SKIP and v is not None})
    adset_base["status"] = "ACTIVE"

    print(" OK")
    print(f"  Campana     : {camp_data['name']}")
    print(f"  Adset       : {adset_data['name']}")
    print(f"  Ad          : {ad_data['name']}")
    print(f"  Programación: status={orig_camp_status}, start={orig_start_time}, stop={orig_stop_time}")
    return {"orig_camp_name":camp_data["name"],"camp_base":camp_base,
            "adset_base":adset_base,"adset_name":adset_data["name"],
            "ad_name":ad_data["name"],"cr_spec":cr_spec,
            "orig_camp_status":orig_camp_status,"orig_start_time":orig_start_time,"orig_stop_time":orig_stop_time,
            "original_creative_id": ORIG_CREATIVE_ID}  # FIX: reusar creative original

# ── PREFLIGHT (1 batch call por campaña) ──────────────────────────────────────
def preflight_campaign(camp_id):
    print(f"  Preflight (1 batch call)...", end="", flush=True)
    results = api_batch([
        {"method":"GET","relative_url":f"{camp_id}/adsets?fields=id&limit=200"},
        {"method":"GET","relative_url":f"{camp_id}/ads?fields=id,adset_id&limit=200"},
    ])
    adset_ids = set(); adsets_with_ad = set(); ok = True
    if results[0]["code"] == 200:
        for a in results[0]["body"].get("data",[]): adset_ids.add(a["id"])
    else:
        ok = False
    if results[1]["code"] == 200:
        for a in results[1]["body"].get("data",[]): adsets_with_ad.add(a.get("adset_id"))
    else:
        ok = False
    adsets_with_ad.discard(None)
    status = "OK" if ok else "parcial"
    print(f" {status} — {len(adset_ids)} adsets, {len(adsets_with_ad)} con ad")
    return {"adset_ids": adset_ids, "adsets_with_ad": adsets_with_ad, "ok": ok}

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("  META ADS CLONE v2.0 — FULL RUN")
    print("=" * 65)
    print(f"  Cuenta   : {ACCOUNT_ID}")
    print(f"  Guards   : max {CAMPAIGN_ADSET_LIMIT} adsets/campana | max {ADSET_AD_LIMIT} ad/adset")
    print(f"  Multi-ad : {'DESACTIVADO' if not MULTI_ADVERTISER_ADS else 'activado'}")

    print("\n[1/4] Config original")
    cfg = fetch_initial_config()
    orig_camp_name = cfg["orig_camp_name"]

    print("\n[2/4] Estado")
    state = load_state()
    print(f"  State: {'vacio' if not state else list(state.keys())}")

    csv_is_new = not os.path.exists(LOG_CSV)
    csvfile = open(LOG_CSV, "a", newline="", encoding="utf-8", buffering=8192)
    writer  = csv.DictWriter(csvfile, fieldnames=[
        "timestamp","n","i","campaign_id","campaign_name",
        "adset_id","creative_id","ad_id","status","note"])
    if csv_is_new: writer.writeheader(); csvfile.flush()

    print(f"\n[3/4] Creando clon...\n")
    total_ok = total_fail = total_skip = total_guard = 0
    unsaved_changes = 0

    for n in N_VALUES:
        key_camp  = sk_camp(n)
        new_name  = orig_camp_name.replace(NAME_SUFFIX_ORIG, f"#{n}")
        print(f"{'='*65}")
        print(f"  n={n}  ->  {new_name}")

        # Campaña
        if state.get(key_camp, {}).get("campaign_id"):
            camp_id = state[key_camp]["campaign_id"]
            clog("INFO", f"SKIP camp {camp_id}", n=n)
        else:
            # Construir payload de campaña con programación original
            camp_payload = {**cfg["camp_base"], "name": new_name, "status": cfg.get("orig_camp_status", "ACTIVE")}
            if cfg.get("orig_start_time"):
                camp_payload["start_time"] = cfg["orig_start_time"]
            if cfg.get("orig_stop_time"):
                camp_payload["stop_time"] = cfg["orig_stop_time"]
            
            camp_id, err = api_post(f"{ACCOUNT_ID}/campaigns", camp_payload)
            if err:
                print(f"  [FAIL camp] {err.get('message','')}"); continue
            state.setdefault(key_camp, {}).update({"campaign_id":camp_id,"campaign_name":new_name})
            unsaved_changes += 1
            if unsaved_changes >= SAVE_INTERVAL:
                save_state(state); unsaved_changes = 0
            clog("INFO", f"NEW  camp {camp_id}", n=n)
            time.sleep(SLEEP_BETWEEN)

        # Preflight
        pf = preflight_campaign(camp_id)
        existing_adsets = pf["adset_ids"]
        adsets_with_ad  = pf["adsets_with_ad"]
        created_this_run: set = set()

        print(f"  {'─'*58}")

        lock = threading.Lock()

        def process_adset(i):
            nonlocal unsaved_changes, total_ok, total_fail, total_skip, total_guard
            key_as = sk_adset(n, i)
            ts = datetime.now(timezone.utc).isoformat()

            with lock:
                if state.get(key_as, {}).get("ad_id"):
                    clog("SKIP", "SKIP completo (state)", n=n, i=i)
                    total_skip += 1
                    return
            clog("INFO", f"start adset {i}/{ADSETS_PER_CAMP}", n=n, i=i)

            # Guard A — limite adsets
            with lock:
                adsets_in_meta_now = len(existing_adsets) + len(created_this_run)
                need_new_adset = not state.get(key_as, {}).get("adset_id")
            if need_new_adset and adsets_in_meta_now >= CAMPAIGN_ADSET_LIMIT:
                clog("GUARD", f"{adsets_in_meta_now}/{CAMPAIGN_ADSET_LIMIT} adsets. Saltando.", n=n, i=i)
                with lock:
                    total_guard += 1
                    writer.writerow({"timestamp":ts,"n":n,"i":i,"campaign_id":camp_id,
                        "campaign_name":new_name,"adset_id":"","creative_id":"","ad_id":"",
                        "status":"GUARD_CAMP_LIMIT","note":f"{adsets_in_meta_now}/{CAMPAIGN_ADSET_LIMIT}"})
                return

            # Adset
            with lock:
                adset_id = state.get(key_as, {}).get("adset_id")
            if adset_id:
                clog("INFO", "adset skip", n=n, i=i)
            else:
                adset_id, err = api_post(f"{ACCOUNT_ID}/adsets",
                    {**cfg["adset_base"],"campaign_id":camp_id,"name":cfg["adset_name"]})
                if err:
                    msg = err.get("message","")[:60]
                    clog("ERROR", f"adset FAIL: {msg}", n=n, i=i)
                    with lock:
                        total_fail += 1
                        writer.writerow({"timestamp":ts,"n":n,"i":i,"campaign_id":camp_id,
                            "campaign_name":new_name,"adset_id":"","creative_id":"","ad_id":"",
                            "status":"ERR_ADSET","note":msg})
                    time.sleep(SLEEP_BETWEEN)
                    return
                clog("OK", "adset OK", n=n, i=i)
                with lock:
                    state.setdefault(key_as, {})["adset_id"] = adset_id
                    unsaved_changes += 1
                    created_this_run.add(adset_id)
                    if unsaved_changes >= SAVE_INTERVAL:
                        save_state(state); unsaved_changes = 0
                time.sleep(SLEEP_BETWEEN)

            # Guard B — adset ya tiene ad
            with lock:
                has_ad = adset_id in adsets_with_ad
            if has_ad:
                clog("GUARD", "Adset ya tiene ad. Saltando.", n=n, i=i)
                with lock:
                    total_guard += 1
                    writer.writerow({"timestamp":ts,"n":n,"i":i,"campaign_id":camp_id,
                        "campaign_name":new_name,"adset_id":adset_id,"creative_id":"","ad_id":"",
                        "status":"GUARD_ADSET_HAS_AD","note":"preflight"})
                return

            # Creative — FIX: reusar el creative_id original, no crear uno nuevo.
            # Crear un nuevo creative pierde el historial de aprendizaje de Meta
            # y los social proof (likes/comentarios) del anuncio original.
            with lock:
                cr_id = state.get(key_as, {}).get("creative_id")
            if not cr_id:
                cr_id = cfg["original_creative_id"]
                with lock:
                    state.setdefault(key_as, {})["creative_id"] = cr_id
                    unsaved_changes += 1
                    if unsaved_changes >= SAVE_INTERVAL:
                        save_state(state); unsaved_changes = 0
                clog("INFO", f"creative REUSED {cr_id}", n=n, i=i)
            else:
                clog("INFO", "creative skip", n=n, i=i)

            # Ad
            ad_id, err = api_post(f"{ACCOUNT_ID}/ads", {
                "name":     cfg["ad_name"],
                "adset_id": adset_id,
                "creative": {"creative_id": cr_id},
                "status":   "ACTIVE",
            })
            if err:
                if "NET_UNKNOWN_RESULT" in err.get("message", ""):
                    recovered_ad_id = find_existing_ad_in_adset(adset_id)
                    if recovered_ad_id:
                        clog("WARN", f"ad recover OK {recovered_ad_id}", n=n, i=i)
                        with lock:
                            state.setdefault(key_as, {})["ad_id"] = recovered_ad_id
                            adsets_with_ad.add(adset_id)
                            unsaved_changes += 1
                            total_ok += 1
                            # Guardado inmediato para no volver a crear este slot tras una caida.
                            save_state(state); unsaved_changes = 0
                            writer.writerow({"timestamp":ts,"n":n,"i":i,"campaign_id":camp_id,
                                "campaign_name":new_name,"adset_id":adset_id,"creative_id":cr_id,"ad_id":recovered_ad_id,
                                "status":"OK_RECOVERED","note":"NET_UNKNOWN_RESULT"})
                        time.sleep(SLEEP_BETWEEN)
                        return
                msg = err.get("message","")[:60]
                clog("ERROR", f"ad FAIL: {msg}", n=n, i=i)
                with lock:
                    total_fail += 1
                    writer.writerow({"timestamp":ts,"n":n,"i":i,"campaign_id":camp_id,
                        "campaign_name":new_name,"adset_id":adset_id,"creative_id":cr_id,"ad_id":"",
                        "status":"ERR_AD","note":msg})
                time.sleep(SLEEP_BETWEEN)
                return

            clog("OK", "ad OK", n=n, i=i)
            with lock:
                state.setdefault(key_as, {})["ad_id"] = ad_id
                adsets_with_ad.add(adset_id)
                unsaved_changes += 1
                total_ok += 1
                # Guardado inmediato para minimizar recreaciones si el proceso termina con error.
                save_state(state); unsaved_changes = 0
                writer.writerow({"timestamp":ts,"n":n,"i":i,"campaign_id":camp_id,
                    "campaign_name":new_name,"adset_id":adset_id,"creative_id":cr_id,"ad_id":ad_id,
                    "status":"OK","note":""})
            time.sleep(SLEEP_BETWEEN)

        # Ejecutar tasks en pool
        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            for i in range(1, ADSETS_PER_CAMP + 1):
                futures.append(ex.submit(process_adset, i))
            for f in concurrent.futures.as_completed(futures):
                try:
                    f.result()
                except Exception as e:
                    print(f"[THREAD EXC] {e}")

    csvfile.close()
    if unsaved_changes > 0:
        save_state(state)

    logger.info("=" * 65)
    logger.info("[4/4] RESUMEN")
    logger.info("=" * 65)
    for n in N_VALUES:
        cid = state.get(sk_camp(n), {}).get("campaign_id", "NO CREADA")
        cname = state.get(sk_camp(n), {}).get("campaign_name", "")
        logger.info("  n=%d  campaign_id=%s", n, cid)
        logger.info("        %s", cname)
        for i in range(1, ADSETS_PER_CAMP + 1):
            s = state.get(sk_adset(n, i), {})
            logger.info("        adset=%s  creative=%s  ad=%s",
                         s.get('adset_id','?'), s.get('creative_id','?'), s.get('ad_id','?'))
    logger.info("  OK      : %d", total_ok)
    logger.info("  Skip    : %d", total_skip)
    logger.info("  Guards  : %d", total_guard)
    logger.info("  Fallos  : %d", total_fail)
    logger.info("  State   : %s", STATE_FILE)
    logger.info("  Log CSV : %s", LOG_CSV)

    if total_fail == 0 and total_guard == 0:
        logger.info("  COMPLETO - %d ads en cuenta.", total_ok + total_skip)
    elif total_fail > 0:
        logger.warning("  CON ERRORES (%d) - vuelve a ejecutar para reintentar.", total_fail)

if __name__ == "__main__":
    main()
