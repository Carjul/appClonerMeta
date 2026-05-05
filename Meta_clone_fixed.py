#!/usr/bin/env python3
"""META ADS CLONE - SINGLE CAMPAIGN
Duplica N veces (adicionales) un adset y su ad dentro de una sola campana.
"""

import argparse
import copy
import concurrent.futures
import csv
import io
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone

import logging

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Logging setup ─────────────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT, stream=sys.stdout)
logger = logging.getLogger("meta_clone")


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

# CONFIG
_parser = argparse.ArgumentParser(description="META ADS CLONE - SINGLE CAMPAIGN (multi)")
_parser.add_argument("--campaign-ids", nargs="+", required=True, help="IDs de las campanas a duplicar")
_parser.add_argument("--access-token", required=True, help="Access token de Meta Ads")
_parser.add_argument("--copies-to-create", type=int, default=49, help="Cantidad de copias adicionales por campana")
_parser.add_argument("--campaign-adset-limit", type=int, default=0, help="Limite de adsets por campana (0 = copies+1)")
_args = _parser.parse_args()

ACCESS_TOKEN = _args.access_token
CAMPAIGN_IDS = _args.campaign_ids

if _args.copies_to_create <= 0:
    print("[!] --copies-to-create debe ser mayor a 0")
    sys.exit(1)

if _args.campaign_adset_limit < 0:
    print("[!] --campaign-adset-limit no puede ser negativo")
    sys.exit(1)

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
        data = r.json()
    except requests.RequestException as e:
        logger.error("HTTP exception fetching campaign %s: %s", campaign_id, e)
        raise RuntimeError(f"HTTP error fetching campaign: {e}")

    if isinstance(data, dict) and data.get("error"):
        err = data["error"]
        _log_api_error(f"GET_CAMPAIGN({campaign_id})", err)
        raise RuntimeError(f"API error [{err.get('code')}]: {err.get('message')} | type: {err.get('type')} | fbtrace: {err.get('fbtrace_id')}")

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

if len(CAMPAIGN_IDS) == 0:
    print("[!] No se proporcionaron IDs de campañas.")
    sys.exit(1)
else:
    print(f"[+] Campañas a procesar: {len(CAMPAIGN_IDS)}")

    
RESULT = obtener_campania(CAMPAIGN_IDS[0], ACCESS_TOKEN)

ACCOUNT_ID = RESULT["account_id"]
COPIES_TO_CREATE = int(_args.copies_to_create)
CAMPAIGN_ADSET_LIMIT = int(_args.campaign_adset_limit) if int(_args.campaign_adset_limit) > 0 else COPIES_TO_CREATE + 1
MULTI_ADVERTISER_ADS = False

SLEEP_BETWEEN = 0.6
TRANSIENT_SLEEP = 3.0
TRANSIENT_RETRIES = 4
SAVE_INTERVAL = 10
MAX_WORKERS = 5
SLOT_RETRIES = 5  # reintentos por slot ante errores de red o transitorios

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

API_VER = "v21.0"
BASE_URL = f"https://graph.facebook.com/{API_VER}"

_ADSET_SKIP = {"id", "account_id", "created_time", "updated_time", "campaign_id", "name", "effective_status"}
ADSET_FIELDS = (
    "name,campaign_id,daily_budget,lifetime_budget,bid_amount,bid_strategy,"
    "bid_constraints,billing_event,optimization_goal,targeting,status,"
    "start_time,end_time,pacing_type,promoted_object,destination_type,attribution_spec"
)
CR_FIELDS = "object_story_spec,asset_feed_spec,degrees_of_freedom_spec,url_tags"
SEED_FIELDS = "name,adsets.limit(100){id,name},ads.limit(100){id,name,adset_id,creative{id}}"


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


# Patrones de mensaje que indican que la página no tiene IG conectado
_IG_NO_ACCESS_PATTERNS = (
    "no tiene acceso a instagram",
    "not connected to instagram",
    "no instagram account",
    "no tiene una cuenta de instagram",
    "página no tiene cuenta de instagram",
    "no tiene cuenta de instagram conectada",
    "instagram identity",
    "instagram account is not connected",
)
_IG_NO_ACCESS_SUBCODES = (1487390, 1487079, 1815174)


# PBIA (Page-Backed Instagram Account) — cache para no llamar a la API mas de una vez por pagina
_PAGE_ID = None              # se setea desde fetch_initial_config
_PBIA_CACHE = {}             # page_id -> pbia_id (o None si fallo)
_PBIA_LOCK = threading.Lock()


def _ensure_pbia():
    """Crea (o recupera) la PBIA para _PAGE_ID. Idempotente y cacheada por page_id.
    Retorna el pbia_id si existe/se creo, None si fallo o no hay page_id.
    """
    if not _PAGE_ID:
        logger.error("PBIA: no hay page_id disponible (object_story_spec.page_id no se detecto)")
        return None

    with _PBIA_LOCK:
        if _PAGE_ID in _PBIA_CACHE:
            return _PBIA_CACHE[_PAGE_ID]

        url = f"{BASE_URL}/{_PAGE_ID}/page_backed_instagram_accounts"
        logger.warning("PBIA: creando/obteniendo para page_id=%s", _PAGE_ID)
        try:
            r = requests.post(url, data={"access_token": ACCESS_TOKEN}, timeout=30)
            _log_http_response(f"PBIA_CREATE({_PAGE_ID})", r)
            data = r.json()
        except Exception as e:
            logger.error("PBIA: excepcion al llamar al endpoint: %s", e)
            _PBIA_CACHE[_PAGE_ID] = None
            return None

        if "error" in data:
            _log_api_error(f"PBIA_CREATE({_PAGE_ID})", data["error"])
            _PBIA_CACHE[_PAGE_ID] = None
            return None

        pbia_id = data.get("id")
        _PBIA_CACHE[_PAGE_ID] = pbia_id
        logger.warning("PBIA: OK pbia_id=%s para page_id=%s", pbia_id, _PAGE_ID)
        return pbia_id


def _autofix_payload(payload, err):
    """Ajusta el payload in-place ante errores conocidos de Meta. Devuelve True si modifico algo."""
    if not isinstance(payload, dict):
        return False

    subcode = err.get("error_subcode")
    msg = (err.get("message") or "").lower()
    user_msg = (err.get("error_user_msg") or "").lower()
    user_title = (err.get("error_user_title") or "").lower()
    error_data = str(err.get("error_data") or "")
    full_text = f"{msg} {user_msg} {user_title}"

    targeting = payload.get("targeting")
    if not isinstance(targeting, dict):
        return False

    ig_positions = targeting.get("instagram_positions")
    ig_positions = ig_positions if isinstance(ig_positions, list) else None

    # FIX 1: explore_home requiere explore (subcode 2490392)
    if subcode == 2490392 or ("instagram_positions" in error_data and ("explore" in full_text or "explorar" in full_text)):
        if ig_positions is not None:
            if "explore_home" in ig_positions and "explore" not in ig_positions:
                ig_positions.append("explore")
                logger.warning("AUTOFIX: anadido 'explore' a instagram_positions (subcode 2490392)")
                return True
            if "explore" in ig_positions and "explore_home" not in ig_positions:
                ig_positions.append("explore_home")
                logger.warning("AUTOFIX: anadido 'explore_home' a instagram_positions")
                return True
            if "explore_home" in ig_positions:
                ig_positions.remove("explore_home")
                logger.warning("AUTOFIX: removido 'explore_home' (no pudo emparejarse)")
                return True

    # FIX 2: pagina sin Instagram conectado -> crear PBIA on-demand y reintentar
    # NO se remueve Instagram. En su lugar se crea una Page-Backed Instagram Account
    # (PBIA) para que la fan page pueda publicar en IG sin tener cuenta IG real.
    # La llamada es idempotente y se cachea por page_id, asi se ejecuta solo cuando
    # Meta arroja el error (no preventivamente).
    if subcode in _IG_NO_ACCESS_SUBCODES or any(p in full_text for p in _IG_NO_ACCESS_PATTERNS):
        pbia_id = _ensure_pbia()
        if pbia_id:
            logger.warning("AUTOFIX: PBIA lista (id=%s). Reintentando con misma config.", pbia_id)
            return True
        logger.error(
            "AUTOFIX FAIL: no se pudo crear/obtener PBIA. "
            "Verifica permisos del token (pages_manage_ads, ads_management) "
            "y que la fan page sea elegible para PBIA en Business Manager."
        )
        return False

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

        return [{"code": item.get("code", 0), "body": json.loads(item.get("body", "{}"))} for item in results]


def api_post(endpoint, payload):
    url = f"{BASE_URL}/{endpoint}"
    rl_attempt = 0
    tr_attempt = 0
    autofix_attempts = 0
    MAX_AUTOFIX = 3

    # Trabajar con copia para que el autofix no mute el payload del caller
    payload = copy.deepcopy(payload)

    # Log del payload sin access_token
    logger.info("POST %s | payload_keys=%s", endpoint, list(payload.keys()))
    logger.debug("POST %s | payload=%s", endpoint, json.dumps(payload, ensure_ascii=False, default=str)[:600])

    while True:
        full_payload = {**payload, "access_token": ACCESS_TOKEN}
        try:
            r = requests.post(url, json=full_payload, timeout=30)
            _log_http_response(f"POST({endpoint})", r)
            data = r.json()
        except Exception as e:
            logger.error("POST %s | network exception: %s", endpoint, e)
            return None, {"message": f"NET_UNKNOWN_RESULT: {e}", "code": -1}

        if "error" not in data:
            created_id = data.get("id")
            logger.info("POST %s | SUCCESS id=%s", endpoint, created_id)
            return created_id, None

        err = data["error"]
        _log_api_error(f"POST({endpoint})", err)

        if _is_rate_limit(err) or r.status_code >= 500:
            wait = min(2 ** rl_attempt * 2, 120)
            logger.warning("POST %s | rate-limit/5xx, retry in %ds (rl_attempt=%d)", endpoint, wait, rl_attempt)
            time.sleep(wait)
            rl_attempt += 1
            continue

        if _is_transient(err) and tr_attempt < TRANSIENT_RETRIES:
            tr_attempt += 1
            logger.warning("POST %s | transient error, retry %d/%d", endpoint, tr_attempt, TRANSIENT_RETRIES)
            time.sleep(TRANSIENT_SLEEP)
            continue

        if autofix_attempts < MAX_AUTOFIX and _autofix_payload(payload, err):
            autofix_attempts += 1
            logger.warning("POST %s | autofix aplicado, retry %d/%d", endpoint, autofix_attempts, MAX_AUTOFIX)
            time.sleep(SLEEP_BETWEEN)
            continue

        logger.error("POST %s | FATAL error, no more retries", endpoint)
        return None, err


def load_state(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def find_existing_ad_in_adset(adset_id):
    logger.info("RECOVER checking existing ads in adset %s", adset_id)
    results = api_batch([{"method": "GET", "relative_url": f"{adset_id}/ads?fields=id&limit=2"}])
    if results[0]["code"] != 200:
        logger.warning("RECOVER adset %s lookup failed: HTTP %d", adset_id, results[0]["code"])
        return None
    data = results[0]["body"].get("data", [])
    found = data[0].get("id") if data else None
    logger.info("RECOVER adset %s | found_ad=%s", adset_id, found)
    return found


def sk_adset(i):
    return f"i={i}"


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


def clean_adset_payload(adset):
    payload = copy.deepcopy(adset)

    # PRESERVAR start_time y end_time para mantener la programación original
    # payload.pop("start_time", None)
    # payload.pop("end_time", None)

    if payload.get("destination_type") == "UNDEFINED":
        payload.pop("destination_type")

    if payload.get("lifetime_budget") in ("0", 0):
        payload.pop("lifetime_budget", None)

    targeting = payload.get("targeting", {})
    targeting.pop("age_range", None)

    # FIX: Meta exige que si se usa "explore_home" tambien este "explore"
    ig_positions = targeting.get("instagram_positions", [])
    if "explore_home" in ig_positions and "explore" not in ig_positions:
        ig_positions.append("explore")
        logger.info("AUTO-FIX: added 'explore' to instagram_positions (required by explore_home)")

    promoted = payload.get("promoted_object", {})
    promoted.pop("smart_pse_enabled", None)

    return payload


def resolve_seed_ids_from_campaign(campaign_id):
    print("[1/5] Resolviendo IDs desde campana...", end="", flush=True)
    results = api_batch(
        [
            {
                "method": "GET",
                "relative_url": f"{campaign_id}?fields={SEED_FIELDS}",
            }
        ]
    )

    if results[0]["code"] != 200:
        message = results[0]["body"].get("error", {}).get("message", "")
        raise RuntimeError(f"Error leyendo campana base: {message}")

    body = results[0]["body"]
    ads = body.get("ads", {}).get("data", [])
    adsets = body.get("adsets", {}).get("data", [])

    if not ads:
        raise RuntimeError("La campana no tiene ads para usar como base.")

    base_ad = ads[0]
    ad_id = base_ad.get("id")
    ad_name = base_ad.get("name", "")
    adset_id = base_ad.get("adset_id")
    creative_id = (base_ad.get("creative") or {}).get("id")

    if not adset_id and adsets:
        adset_id = adsets[0].get("id")

    if not adset_id:
        raise RuntimeError("No se pudo resolver adset_id desde la campana.")
    if not ad_id:
        raise RuntimeError("No se pudo resolver ad_id desde la campana.")
    if not creative_id:
        raise RuntimeError("No se pudo resolver creative_id desde la campana.")

    print(" OK")
    print(f"  Campana  : {campaign_id}")
    print(f"  Adset ID : {adset_id}")
    print(f"  Ad ID    : {ad_id}")
    print(f"  Creative : {creative_id}")

    return {
        "adset_id": adset_id,
        "ad_id": ad_id,
        "ad_name": ad_name,
        "creative_id": creative_id,
    }


def fetch_initial_config(campaign_id):
    seed = resolve_seed_ids_from_campaign(campaign_id)

    print("[2/5] Setup inicial (1 batch call)...", end="", flush=True)
    results = api_batch(
        [
            {"method": "GET", "relative_url": f"{seed['adset_id']}?fields={ADSET_FIELDS}"},
            {"method": "GET", "relative_url": f"{seed['ad_id']}?fields=name"},
            {"method": "GET", "relative_url": f"{seed['creative_id']}?fields={CR_FIELDS}"},
        ]
    )

    labels = ["adset", "ad", "creative"]
    for idx, label in enumerate(labels):
        if results[idx]["code"] != 200:
            message = results[idx]["body"].get("error", {}).get("message", "")
            raise RuntimeError(f"Error leyendo {label}: {message}")

    adset_data = results[0]["body"]
    ad_data = results[1]["body"]
    cr_spec = clean_creative_spec(results[2]["body"])

    # Detectar page_id para autofix de PBIA (solo se usa si Meta lanza el error de "no IG")
    global _PAGE_ID
    osp = cr_spec.get("object_story_spec") or {}
    detected_page_id = osp.get("page_id")
    if detected_page_id:
        _PAGE_ID = detected_page_id
        logger.info("PAGE_ID detectado para PBIA on-demand: %s", _PAGE_ID)
    else:
        logger.warning("PAGE_ID no detectado en object_story_spec (PBIA no estara disponible si Meta lanza error de no-IG)")

    # Capturar estado y programación original
    orig_status = adset_data.get("status", "ACTIVE")
    orig_start_time = adset_data.get("start_time")
    orig_end_time = adset_data.get("end_time")

    adset_base = clean_adset_payload({k: v for k, v in adset_data.items() if k not in _ADSET_SKIP and v is not None})
    # Preservar el estado original en lugar de forzar ACTIVE
    adset_base["status"] = orig_status

    print(" OK")
    print(f"  Campana     : {campaign_id}")
    print(f"  Adset       : {adset_data['name']}")
    print(f"  Ad          : {ad_data['name']}")
    print(f"  Programación: status={orig_status}, start={orig_start_time}, end={orig_end_time}")

    return {
        "adset_base": adset_base,
        "adset_name": adset_data["name"],
        "ad_name": ad_data["name"],
        "cr_spec": cr_spec,
        "orig_status": orig_status,
        "orig_start_time": orig_start_time,
        "orig_end_time": orig_end_time,
        "original_creative_id": seed["creative_id"],  # FIX: reusar creative original
    }


def preflight_campaign(camp_id):
    print("[2/4] Preflight (1 batch call)...", end="", flush=True)
    results = api_batch(
        [
            {"method": "GET", "relative_url": f"{camp_id}/adsets?fields=id&limit=200"},
            {"method": "GET", "relative_url": f"{camp_id}/ads?fields=id,adset_id&limit=200"},
        ]
    )

    adset_ids = set()
    adsets_with_ad = set()
    ok = True

    if results[0]["code"] == 200:
        for item in results[0]["body"].get("data", []):
            adset_ids.add(item["id"])
    else:
        ok = False

    if results[1]["code"] == 200:
        for item in results[1]["body"].get("data", []):
            adsets_with_ad.add(item.get("adset_id"))
    else:
        ok = False

    adsets_with_ad.discard(None)
    status = "OK" if ok else "parcial"
    print(f" {status} - {len(adset_ids)} adsets, {len(adsets_with_ad)} con ad")
    return {"adset_ids": adset_ids, "adsets_with_ad": adsets_with_ad}


def run_for_campaign(campaign_id):
    state_file = os.path.join(LOG_DIR, f"meta_single_clone_state_{campaign_id}.json")
    log_csv = os.path.join(LOG_DIR, f"meta_single_clone_log_{campaign_id}.csv")

    print(f"  Campana     : {campaign_id}")
    print(f"  Objetivo    : crear {COPIES_TO_CREATE} copias adicionales")
    print(f"  Limite set  : {CAMPAIGN_ADSET_LIMIT} adsets por campana")
    print(f"  Workers     : {MAX_WORKERS}")
    print(f"  Multi-ad    : {'DESACTIVADO' if not MULTI_ADVERTISER_ADS else 'activado'}")

    cfg = fetch_initial_config(campaign_id)
    state = load_state(state_file)
    preflight = preflight_campaign(campaign_id)

    existing_adsets = preflight["adset_ids"]
    adsets_with_ad = preflight["adsets_with_ad"]
    created_this_run = set()

    csv_is_new = not os.path.exists(log_csv)
    csvfile = open(log_csv, "a", newline="", encoding="utf-8", buffering=8192)
    writer = csv.DictWriter(
        csvfile,
        fieldnames=["timestamp", "i", "campaign_id", "adset_id", "creative_id", "ad_id", "status", "note"],
    )
    if csv_is_new:
        writer.writeheader()
        csvfile.flush()

    print("[4/5] Creando copias...")
    total_ok = 0
    total_fail = 0
    total_skip = 0
    total_guard = 0
    unsaved_changes = 0
    lock = threading.Lock()

    def process_copy(i):
        nonlocal total_ok, total_fail, total_skip, total_guard, unsaved_changes

        key = sk_adset(i)

        # Si ya está completo desde una ejecución anterior, saltar
        with lock:
            if state.get(key, {}).get("ad_id"):
                print(f"  i={i:02d} SKIP completo (state)")
                total_skip += 1
                return

        for attempt in range(1, SLOT_RETRIES + 1):
            ts = datetime.now(timezone.utc).isoformat()
            logger.debug("SLOT i=%d attempt=%d/%d started", i, attempt, SLOT_RETRIES)

            # Guard A — límite adsets (permanente, sin retry)
            with lock:
                adsets_in_meta_now = len(existing_adsets) + len(created_this_run)
                need_new_adset = not state.get(key, {}).get("adset_id")
            if need_new_adset and adsets_in_meta_now >= CAMPAIGN_ADSET_LIMIT:
                note = f"{adsets_in_meta_now}/{CAMPAIGN_ADSET_LIMIT}"
                print(f"  i={i:02d} GUARD camp limit {note}")
                with lock:
                    total_guard += 1
                    writer.writerow({"timestamp": ts, "i": i, "campaign_id": campaign_id,
                        "adset_id": "", "creative_id": "", "ad_id": "",
                        "status": "GUARD_CAMP_LIMIT", "note": note})
                return

            # ── Adset ──────────────────────────────────────────────────────
            with lock:
                adset_id = state.get(key, {}).get("adset_id")

            if not adset_id:
                # Construir payload con programaci\u00f3n original si existe
                adset_payload = {**cfg["adset_base"], "campaign_id": campaign_id, "name": cfg["adset_name"]}
                if cfg.get("orig_start_time"):
                    adset_payload["start_time"] = cfg["orig_start_time"]
                if cfg.get("orig_end_time"):
                    adset_payload["end_time"] = cfg["orig_end_time"]
                
                adset_id, err = api_post(
                    f"{ACCOUNT_ID}/adsets",
                    adset_payload,
                )
                if err:
                    msg = err.get("message", "")
                    print(f"  i={i:02d} ERR_ADSET [{attempt}/{SLOT_RETRIES}] {msg[:80]}")
                    if attempt < SLOT_RETRIES:
                        time.sleep(TRANSIENT_SLEEP * attempt)
                        continue
                    with lock:
                        total_fail += 1
                        writer.writerow({"timestamp": ts, "i": i, "campaign_id": campaign_id,
                            "adset_id": "", "creative_id": "", "ad_id": "",
                            "status": "ERR_ADSET", "note": msg[:120]})
                    return
                with lock:
                    state.setdefault(key, {})["adset_id"] = adset_id
                    created_this_run.add(adset_id)
                    unsaved_changes += 1
                    print(f"  i={i:02d} adset OK {adset_id}")
                    if unsaved_changes >= SAVE_INTERVAL:
                        save_state(state, state_file)
                        unsaved_changes = 0
                time.sleep(SLEEP_BETWEEN)

            # Guard B — adset ya tiene ad (permanente, sin retry)
            with lock:
                if adset_id in adsets_with_ad:
                    print(f"  i={i:02d} GUARD adset ya tiene ad")
                    total_guard += 1
                    writer.writerow({"timestamp": ts, "i": i, "campaign_id": campaign_id,
                        "adset_id": adset_id, "creative_id": "", "ad_id": "",
                        "status": "GUARD_ADSET_HAS_AD", "note": "preflight"})
                    return
                cr_id = state.get(key, {}).get("creative_id")

            # ── Creative ───────────────────────────────────────────────────
            # FIX: Reusar siempre el creative_id original. No crear uno nuevo.
            # Crear un nuevo creative genera un ID distinto, pierde el historial
            # de aprendizaje de Meta y los social proof (likes/comentarios).
            if not cr_id:
                cr_id = cfg["original_creative_id"]
                with lock:
                    state.setdefault(key, {})["creative_id"] = cr_id
                    unsaved_changes += 1
                    print(f"  i={i:02d} creative REUSED {cr_id}")
                    if unsaved_changes >= SAVE_INTERVAL:
                        save_state(state, state_file)
                        unsaved_changes = 0

            # ── Ad ─────────────────────────────────────────────────────────
            ad_id, err = api_post(
                f"{ACCOUNT_ID}/ads",
                {
                    "name": cfg["ad_name"],
                    "adset_id": adset_id,
                    "creative": {"creative_id": cr_id},
                    "status": "ACTIVE",
                },
            )
            if err:
                msg = err.get("message", "")
                if "NET_UNKNOWN_RESULT" in msg:
                    # No sabemos si Meta creó el ad; intentar recuperarlo
                    recovered = find_existing_ad_in_adset(adset_id)
                    if recovered:
                        ad_id = recovered
                        print(f"  i={i:02d} ad RECOVER {ad_id}")
                    else:
                        print(f"  i={i:02d} ERR_AD NET [{attempt}/{SLOT_RETRIES}] {msg[:80]}")
                        if attempt < SLOT_RETRIES:
                            time.sleep(TRANSIENT_SLEEP * attempt)
                            continue
                        with lock:
                            total_fail += 1
                            writer.writerow({"timestamp": ts, "i": i, "campaign_id": campaign_id,
                                "adset_id": adset_id, "creative_id": cr_id, "ad_id": "",
                                "status": "ERR_AD", "note": msg[:120]})
                        return
                else:
                    print(f"  i={i:02d} ERR_AD [{attempt}/{SLOT_RETRIES}] {msg[:80]}")
                    if attempt < SLOT_RETRIES:
                        time.sleep(TRANSIENT_SLEEP * attempt)
                        continue
                    with lock:
                        total_fail += 1
                        writer.writerow({"timestamp": ts, "i": i, "campaign_id": campaign_id,
                            "adset_id": adset_id, "creative_id": cr_id, "ad_id": "",
                            "status": "ERR_AD", "note": msg[:120]})
                    return

            # ── Éxito ──────────────────────────────────────────────────────
            with lock:
                state.setdefault(key, {})["ad_id"] = ad_id
                adsets_with_ad.add(adset_id)
                unsaved_changes += 1
                total_ok += 1
                print(f"  i={i:02d} ad OK {ad_id}")
                writer.writerow({"timestamp": ts, "i": i, "campaign_id": campaign_id,
                    "adset_id": adset_id, "creative_id": cr_id, "ad_id": ad_id,
                    "status": "OK", "note": ""})
                if unsaved_changes >= SAVE_INTERVAL:
                    save_state(state, state_file)
                    unsaved_changes = 0
            time.sleep(SLEEP_BETWEEN)
            return  # éxito, salir del loop de reintentos

    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for i in range(1, COPIES_TO_CREATE + 1):
            futures.append(ex.submit(process_copy, i))
        for f in concurrent.futures.as_completed(futures):
            try:
                f.result()
            except Exception as e:
                with lock:
                    print(f"  THREAD ERROR: {e}")
                total_fail += 1

    if unsaved_changes > 0:
        save_state(state, state_file)

    csvfile.close()

    logger.info("=" * 65)
    logger.info("[5/5] RESUMEN para campaign %s", campaign_id)
    logger.info("=" * 65)
    logger.info("  OK      : %d", total_ok)
    logger.info("  Skip    : %d", total_skip)
    logger.info("  Guards  : %d", total_guard)
    logger.info("  Fallos  : %d", total_fail)
    logger.info("  State   : %s", state_file)
    logger.info("  Log CSV : %s", log_csv)

    if total_fail == 0 and total_guard == 0:
        logger.info("  COMPLETO - %d nuevas copias creadas.", total_ok)
    elif total_fail > 0:
        logger.warning("  CON ERRORES - vuelve a ejecutar para reintentar.")


def main():
    print("=" * 65)
    print("  META ADS CLONE - SINGLE CAMPAIGN (MULTI)")
    print("=" * 65)
    print(f"  Cuenta      : {ACCOUNT_ID}")
    print(f"  Campanas    : {len(CAMPAIGN_IDS)}")
    print(f"  Objetivo    : {COPIES_TO_CREATE} copias por campana")
    for campaign_id in CAMPAIGN_IDS:
        print(f"\n{'='*65}")
        run_for_campaign(campaign_id)


if __name__ == "__main__":
    main()
