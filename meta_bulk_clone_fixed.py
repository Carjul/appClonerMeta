#!/usr/bin/env python3
"""META ADS CLONE v2.0 — FULL RUN
Clonar una campaña base en N campañas × N adsets × N ads por adset.
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
_parser.add_argument("--copies", type=int, default=4, help="Cantidad de campañas clonadas a crear")
_parser.add_argument("--start-copy", type=int, default=2, help="Numero inicial del sufijo #N")
_parser.add_argument("--adsets-per-campaign", type=int, default=50, help="Adsets a crear por cada campaña clonada")
_parser.add_argument("--ads-per-adset", type=int, default=1, help="Ads a crear dentro de cada adset nuevo")
_parser.add_argument("--max-workers", type=int, default=5, help="Numero de hilos para paralelismo")
_args = _parser.parse_args()

if _args.copies <= 0:
    _parser.error("--copies debe ser mayor a 0")
if _args.adsets_per_campaign <= 0:
    _parser.error("--adsets-per-campaign debe ser mayor a 0")
if _args.ads_per_adset <= 0:
    _parser.error("--ads-per-adset debe ser mayor a 0")
if _args.max_workers <= 0:
    _parser.error("--max-workers debe ser mayor a 0")

ACCESS_TOKEN     = _args.access_token
ORIG_CAMPAIGN_ID = _args.campaign_id

def obtener_campania(campaign_id: str, access_token: str, ads_per_adset: int, api_version: str = "v23.0") -> dict:
   
    fields = (
        "account_id,name,status,"
        "adsets.limit(100){name,status,daily_budget,lifetime_budget,billing_event,optimization_goal,targeting,promoted_object,bid_strategy},"
        f"ads.limit({max(100, ads_per_adset)}){{name,status,creative{{id}},adset_id}}"
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

    adsets = data.get("adsets", {}).get("data", []) if isinstance(data.get("adsets"), dict) else []
    if not adsets:
        raise RuntimeError("La campaña original no tiene adsets para usar como plantilla")

    first_adset = adsets[0]
    first_adset_id = first_adset.get("id")
    ads = data.get("ads", {}).get("data", []) if isinstance(data.get("ads"), dict) else []
    source_ads = [ad for ad in ads if ad.get("adset_id") == first_adset_id]
    if len(source_ads) < ads_per_adset:
        raise RuntimeError(
            f"El adset original {first_adset_id} tiene {len(source_ads)} ads, "
            f"pero pediste --ads-per-adset {ads_per_adset}"
        )
    source_ads = source_ads[:ads_per_adset]
    for idx, ad in enumerate(source_ads, start=1):
        if not (ad.get("creative") or {}).get("id"):
            raise RuntimeError(f"El anuncio fuente #{idx} no tiene creative_id")

    return {
        "name": data.get("name"),
        "campaign_id": campaign_id,
        "account_id": account,
        "adset_id": first_adset_id,
        "source_ads": [
            {
                "ad_id": ad.get("id"),
                "ad_name": ad.get("name") or f"Ad {idx}",
                "creative_id": (ad.get("creative") or {}).get("id"),
            }
            for idx, ad in enumerate(source_ads, start=1)
        ],
        "raw": data,
    }

result = obtener_campania(ORIG_CAMPAIGN_ID, ACCESS_TOKEN, _args.ads_per_adset)

ACCOUNT_ID       = result["account_id"]

ORIG_ADSET_ID    = result["adset_id"]
SOURCE_ADS       = result["source_ads"]

NAME_SUFFIX_ORIG  = "#1"
N_VALUES          = list(range(_args.start_copy, _args.start_copy + _args.copies))
ADSETS_PER_CAMP   = _args.adsets_per_campaign

CAMPAIGN_ADSET_LIMIT = ADSETS_PER_CAMP
ADSET_AD_LIMIT       = _args.ads_per_adset
MULTI_ADVERTISER_ADS = False   # False = OPT_OUT, True = OPT_IN (desde ago 2024 es OPT_IN por defecto)

SLEEP_BETWEEN     = 0.6
TRANSIENT_SLEEP   = 3.0
TRANSIENT_RETRIES = 4
SAVE_INTERVAL     = 20  # checkpoint de estado cada N cambios (reduce I/O)
MAX_WORKERS       = _args.max_workers   # número de hilos para paralelismo (ajustable)

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


# Patrones de mensaje que indican que la pagina no tiene IG conectado
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
    rl_attempt = tr_attempt = autofix_attempts = 0
    MAX_AUTOFIX = 3
    # Trabajar con copia para que el autofix no mute el payload del caller
    payload = copy.deepcopy(payload)
    # Log del payload sin access_token
    logger.info("POST %s | payload_keys=%s", endpoint, list(payload.keys()))
    logger.debug("POST %s | payload=%s", endpoint, json.dumps(payload, ensure_ascii=False, default=str)[:600])
    while True:
        pl = {**payload, "access_token": ACCESS_TOKEN}
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
        if autofix_attempts < MAX_AUTOFIX and _autofix_payload(payload, err):
            autofix_attempts += 1
            logger.warning("POST %s | autofix aplicado, retry %d/%d", endpoint, autofix_attempts, MAX_AUTOFIX)
            time.sleep(SLEEP_BETWEEN); continue
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
def sk_ad(n, i, ad_index): return f"n={n}_i={i}_ad={ad_index}"

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
    first_creative_id = SOURCE_ADS[0]["creative_id"]
    results = api_batch([
        {"method":"GET","relative_url":f"{ORIG_CAMPAIGN_ID}?fields={CAMP_FIELDS}"},
        {"method":"GET","relative_url":f"{ORIG_ADSET_ID}?fields={ADSET_FIELDS}"},
        {"method":"GET","relative_url":f"{first_creative_id}?fields={CR_FIELDS}"},
    ])
    for idx, label in enumerate(["campaign","adset","creative"]):
        if results[idx]["code"] != 200:
            raise RuntimeError(f"Error leyendo {label}: {results[idx]['body'].get('error',{}).get('message')}")
    camp_data  = results[0]["body"]
    adset_data = results[1]["body"]
    cr_spec    = clean_creative_spec(results[2]["body"])

    # Detectar page_id para autofix de PBIA (solo se usa si Meta lanza el error de "no IG")
    global _PAGE_ID
    osp = cr_spec.get("object_story_spec") or {}
    detected_page_id = osp.get("page_id")
    if detected_page_id:
        _PAGE_ID = detected_page_id
        logger.info("PAGE_ID detectado para PBIA on-demand: %s", _PAGE_ID)
    else:
        logger.warning("PAGE_ID no detectado en object_story_spec (PBIA no estara disponible si Meta lanza error de no-IG)")

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
    print(f"  Ads fuente  : {len(SOURCE_ADS)}")
    print(f"  Programación: status={orig_camp_status}, start={orig_start_time}, stop={orig_stop_time}")
    return {"orig_camp_name":camp_data["name"],"camp_base":camp_base,
            "adset_base":adset_base,"adset_name":adset_data["name"],
            "source_ads":SOURCE_ADS,"cr_spec":cr_spec,
            "orig_camp_status":orig_camp_status,"orig_start_time":orig_start_time,"orig_stop_time":orig_stop_time,
            }

# ── PREFLIGHT (1 batch call por campaña) ──────────────────────────────────────
def preflight_campaign(camp_id):
    print(f"  Preflight (1 batch call)...", end="", flush=True)
    results = api_batch([
        {"method":"GET","relative_url":f"{camp_id}/adsets?fields=id&limit=200"},
        {"method":"GET","relative_url":f"{camp_id}/ads?fields=id,adset_id&limit=200"},
    ])
    adset_ids = set(); ads_by_adset = {}; ok = True
    if results[0]["code"] == 200:
        for a in results[0]["body"].get("data",[]): adset_ids.add(a["id"])
    else:
        ok = False
    if results[1]["code"] == 200:
        for a in results[1]["body"].get("data",[]):
            adset_id = a.get("adset_id")
            if adset_id:
                ads_by_adset.setdefault(adset_id, []).append(a.get("id"))
    else:
        ok = False
    status = "OK" if ok else "parcial"
    print(f" {status} — {len(adset_ids)} adsets, {sum(len(v) for v in ads_by_adset.values())} ads")
    return {"adset_ids": adset_ids, "ads_by_adset": ads_by_adset, "ok": ok}

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
        ads_by_adset  = pf["ads_by_adset"]
        created_this_run: set = set()

        print(f"  {'─'*58}")

        lock = threading.Lock()

        def process_adset(i):
            nonlocal unsaved_changes, total_ok, total_fail, total_skip, total_guard
            key_as = sk_adset(n, i)
            ts = datetime.now(timezone.utc).isoformat()

            with lock:
                adset_state = state.get(key_as, {})
                complete_ads = all(state.get(sk_ad(n, i, ad_index), {}).get("ad_id") for ad_index in range(1, ADSET_AD_LIMIT + 1))
                if adset_state.get("adset_id") and complete_ads:
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

            # Ads — reusar los creative_id originales, uno por cada anuncio fuente.
            with lock:
                existing_ads_count = len(ads_by_adset.get(adset_id, []))
            if existing_ads_count >= ADSET_AD_LIMIT:
                clog("GUARD", f"Adset ya tiene {existing_ads_count}/{ADSET_AD_LIMIT} ads. Saltando.", n=n, i=i)
                with lock:
                    total_guard += 1
                    writer.writerow({"timestamp":ts,"n":n,"i":i,"campaign_id":camp_id,
                        "campaign_name":new_name,"adset_id":adset_id,"creative_id":"","ad_id":"",
                        "status":"GUARD_ADSET_HAS_ADS","note":f"preflight {existing_ads_count}/{ADSET_AD_LIMIT}"})
                return

            for ad_index, source_ad in enumerate(cfg["source_ads"], start=1):
                key_ad = sk_ad(n, i, ad_index)
                with lock:
                    saved_ad_id = state.get(key_ad, {}).get("ad_id")
                if saved_ad_id:
                    clog("SKIP", f"ad {ad_index}/{ADSET_AD_LIMIT} skip", n=n, i=i)
                    total_skip += 1
                    continue
                if ad_index <= existing_ads_count:
                    clog("GUARD", f"ad {ad_index}/{ADSET_AD_LIMIT} existe en Meta (preflight)", n=n, i=i)
                    total_guard += 1
                    continue

                cr_id = source_ad["creative_id"]
                with lock:
                    state.setdefault(key_ad, {})["creative_id"] = cr_id
                    unsaved_changes += 1
                    if unsaved_changes >= SAVE_INTERVAL:
                        save_state(state); unsaved_changes = 0
                clog("INFO", f"creative REUSED {cr_id} ad {ad_index}/{ADSET_AD_LIMIT}", n=n, i=i)

                ad_id, err = api_post(f"{ACCOUNT_ID}/ads", {
                    "name":     source_ad["ad_name"],
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
                                state.setdefault(key_ad, {})["ad_id"] = recovered_ad_id
                                ads_by_adset.setdefault(adset_id, []).append(recovered_ad_id)
                                unsaved_changes += 1
                                total_ok += 1
                                save_state(state); unsaved_changes = 0
                                writer.writerow({"timestamp":ts,"n":n,"i":i,"campaign_id":camp_id,
                                    "campaign_name":new_name,"adset_id":adset_id,"creative_id":cr_id,"ad_id":recovered_ad_id,
                                    "status":"OK_RECOVERED","note":f"ad_index={ad_index} NET_UNKNOWN_RESULT"})
                            time.sleep(SLEEP_BETWEEN)
                            continue
                    msg = err.get("message","")[:60]
                    clog("ERROR", f"ad {ad_index}/{ADSET_AD_LIMIT} FAIL: {msg}", n=n, i=i)
                    with lock:
                        total_fail += 1
                        writer.writerow({"timestamp":ts,"n":n,"i":i,"campaign_id":camp_id,
                            "campaign_name":new_name,"adset_id":adset_id,"creative_id":cr_id,"ad_id":"",
                            "status":"ERR_AD","note":f"ad_index={ad_index} {msg}"})
                    time.sleep(SLEEP_BETWEEN)
                    continue

                clog("OK", f"ad {ad_index}/{ADSET_AD_LIMIT} OK", n=n, i=i)
                with lock:
                    state.setdefault(key_ad, {})["ad_id"] = ad_id
                    ads_by_adset.setdefault(adset_id, []).append(ad_id)
                    unsaved_changes += 1
                    total_ok += 1
                    save_state(state); unsaved_changes = 0
                    writer.writerow({"timestamp":ts,"n":n,"i":i,"campaign_id":camp_id,
                        "campaign_name":new_name,"adset_id":adset_id,"creative_id":cr_id,"ad_id":ad_id,
                        "status":"OK","note":f"ad_index={ad_index}"})
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
            logger.info("        adset=%s", s.get('adset_id','?'))
            for ad_index in range(1, ADSET_AD_LIMIT + 1):
                a = state.get(sk_ad(n, i, ad_index), {})
                logger.info("          ad[%d] creative=%s  ad=%s",
                             ad_index, a.get('creative_id','?'), a.get('ad_id','?'))
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
