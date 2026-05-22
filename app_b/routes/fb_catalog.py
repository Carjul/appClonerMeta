import csv
import io
import json
import os
import secrets
import tempfile
from typing import Any, List, Optional
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app_b.db import (
    configs_col,
    fb_campaign_templates_col,
    fb_campaigns_col,
    fb_catalogs_col,
    fb_copy_bundles_col,
    fb_language_carnadas_col,
    fb_media_assets_col,
    fb_planned_campaigns_col,
    fb_product_sets_col,
    fb_products_col,
)
from app_b.services.fb_catalog_notifications import notify_fb_catalog
from app_b.utils import now_iso, oid, serialize_doc


router = APIRouter(prefix="/api/fb-catalog", tags=["fb-catalog"])
public_router = APIRouter(tags=["fb-catalog-feed"])

GRAPH = "https://graph.facebook.com/v21.0"
FEED_COLS = ["id", "title", "description", "availability", "condition", "price", "link", "image_link", "brand", "video[0].url"]

META_LOCALES = [
    {"id": 6, "code": "en_XX", "name": "Ingles (US)"},
    {"id": 24, "code": "en_GB", "name": "Ingles (Reino Unido)"},
    {"id": 5, "code": "es_LA", "name": "Espanol (Latinoamerica)"},
    {"id": 23, "code": "es_ES", "name": "Espanol (Espana)"},
    {"id": 3, "code": "es_MX", "name": "Espanol (Mexico)"},
    {"id": 9, "code": "fr_FR", "name": "Frances"},
    {"id": 44, "code": "fr_CA", "name": "Frances (Canada)"},
    {"id": 17, "code": "ru_RU", "name": "Ruso"},
    {"id": 11, "code": "ja_JP", "name": "Japones"},
    {"id": 28, "code": "ar_AR", "name": "Arabe"},
    {"id": 10, "code": "de_DE", "name": "Aleman"},
    {"id": 16, "code": "it_IT", "name": "Italiano"},
    {"id": 4, "code": "pt_BR", "name": "Portugues (Brasil)"},
    {"id": 15, "code": "pt_PT", "name": "Portugues (Portugal)"},
    {"id": 19, "code": "tr_TR", "name": "Turco"},
    {"id": 12, "code": "ko_KR", "name": "Coreano"},
    {"id": 8, "code": "zh_CN", "name": "Chino (simplificado)"},
    {"id": 31, "code": "zh_TW", "name": "Chino (tradicional)"},
]


class CatalogCreate(BaseModel):
    configId: Optional[str] = None
    name: str = Field(min_length=1)
    businessId: Optional[str] = ""
    pixelId: Optional[str] = ""
    syncToMeta: bool = False


class ProductRow(BaseModel):
    id: Optional[str] = None
    retailerId: str = ""
    title: str = ""
    description: str = ""
    availability: str = "in stock"
    price: str = "10.00 USD"
    link: str = ""
    imageLink: str = ""
    brand: str = "Brand"
    videoUrl: Optional[str] = ""
    videoLabel: Optional[str] = ""
    tag: str = "dirty"


class ProductsBulkSave(BaseModel):
    rows: List[ProductRow]


class ProductSetCreate(BaseModel):
    name: Optional[str] = ""
    productIds: List[str]
    syncToMeta: bool = False
    configId: Optional[str] = None


class SetupDefaultsUpdate(BaseModel):
    businessId: Optional[str] = ""
    adAccountId: Optional[str] = ""
    pageId: Optional[str] = ""
    pixelId: Optional[str] = ""
    telegramBotToken: Optional[str] = ""
    telegramChatId: Optional[str] = ""
    slackWebhookUrl: Optional[str] = ""
    notifyOnApproval: bool = True
    notifyOnConversion: bool = True


class MediaAssetPayload(BaseModel):
    configId: Optional[str] = None
    name: str = Field(min_length=1)
    type: str = Field(pattern="^(image|video)$")
    publicUrl: str = Field(min_length=1)
    notes: Optional[str] = ""
    isDefault: bool = False


class MediaUploadRequest(BaseModel):
    configId: Optional[str] = None
    adAccountId: Optional[str] = ""


class BulkIdsPayload(BaseModel):
    ids: List[str]


class CarnadaPayload(BaseModel):
    configId: Optional[str] = None
    localeId: int
    body: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: Optional[str] = ""
    url: str = Field(min_length=1)
    notes: Optional[str] = ""


class CopyBundlePayload(BaseModel):
    configId: Optional[str] = None
    name: str = Field(min_length=1)
    realBody: str = ""
    realTitle: str = ""
    realDesc: str = ""
    realUrl: str = ""
    targetLocaleId: int = 6
    carnadaIds: List[str] = []


class NormalCampaignAd(BaseModel):
    mediaAssetId: str
    body: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: Optional[str] = ""
    link: str = Field(min_length=1)
    ctaType: str = "LEARN_MORE"
    adName: Optional[str] = ""


class LanguageCampaignAd(BaseModel):
    mediaAssetId: str
    defaultMediaId: str
    copyBundleId: str
    ctaType: str = "LEARN_MORE"
    adName: Optional[str] = ""


class CampaignBase(BaseModel):
    configId: str
    name: str = Field(min_length=1)
    adAccountId: Optional[str] = ""
    pageId: Optional[str] = ""
    pixelId: Optional[str] = ""
    instagramId: Optional[str] = ""
    cboOrAbo: str = Field(default="ABO", pattern="^(ABO|CBO)$")
    dailyBudgetUsd: float = Field(default=5.0, gt=0)
    bidStrategy: str = "LOWEST_COST_WITHOUT_CAP"
    bidAmountUsd: float = 0
    roasFloor: float = 0
    countries: str = "US"
    ageMin: int = 18
    ageMax: int = 65
    localeIds: List[int] = [6]
    objective: str = "OUTCOME_SALES"
    optimizationGoal: str = "OFFSITE_CONVERSIONS"
    customEventType: str = "PURCHASE"
    urlTags: Optional[str] = ""
    adsetName: Optional[str] = ""
    adName: Optional[str] = ""
    startTime: Optional[str] = ""
    endTime: Optional[str] = ""
    budgetType: str = Field(default="daily", pattern="^(daily|lifetime)$")
    spendCapUsd: float = 0
    trickEnabled: bool = False


class NormalCampaignPayload(CampaignBase):
    ads: List[NormalCampaignAd]


class LanguageCampaignPayload(CampaignBase):
    ads: List[LanguageCampaignAd]


class CatalogCampaignPayload(CampaignBase):
    productSetId: str
    lander: str = Field(min_length=1)
    message: str = "{{product.description}}"
    headline: str = "{{product.name}}"
    linkDescription: str = ""
    ctaType: str = "LEARN_MORE"
    useVideo: bool = True
    multiAdvertiserOptout: bool = True


class TemplatePayload(BaseModel):
    configId: Optional[str] = None
    name: str = Field(min_length=1)
    campaignType: str = Field(pattern="^(normal|language|catalog)$")
    config: dict[str, Any] = {}


class PlannedCampaignPayload(BaseModel):
    configId: str
    campaignType: str = Field(pattern="^(normal|language|catalog)$")
    name: str = Field(min_length=1)
    config: dict[str, Any]
    scheduledAt: Optional[str] = ""


def _get_config(config_id: str | None) -> dict | None:
    if not config_id:
        return None
    cfg = configs_col.find_one({"_id": oid(config_id)})
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    return cfg


def _token_for_config(config_id: str | None) -> str:
    cfg = _get_config(config_id)
    token = (cfg or {}).get("access_token")
    if not token:
        raise HTTPException(status_code=400, detail="Config token not found")
    return token


def _meta_post(path: str, token: str, data: dict) -> dict:
    res = requests.post(f"{GRAPH}/{path.lstrip('/')}", params={"access_token": token}, data=data, timeout=60)
    try:
        payload = res.json()
    except ValueError:
        payload = {"error": {"message": res.text[:300]}}
    if res.status_code >= 400 or payload.get("error"):
        err = payload.get("error", {}) if isinstance(payload, dict) else {}
        raise HTTPException(status_code=400, detail=err.get("error_user_msg") or err.get("message") or payload)
    return payload


def _meta_get(path: str, token: str, params: dict | None = None) -> dict:
    res = requests.get(f"{GRAPH}/{path.lstrip('/')}", params={**(params or {}), "access_token": token}, timeout=60)
    try:
        payload = res.json()
    except ValueError:
        payload = {"error": {"message": res.text[:300]}}
    if res.status_code >= 400 or payload.get("error"):
        err = payload.get("error", {}) if isinstance(payload, dict) else {}
        raise HTTPException(status_code=400, detail=err.get("error_user_msg") or err.get("message") or payload)
    return payload


def _meta_get_safe(path: str, token: str, params: dict | None = None) -> dict:
    try:
        return _meta_get(path, token, params)
    except HTTPException:
        return {"data": []}


def _merge_meta_rows(*groups: list[dict]) -> list[dict]:
    by_id = {}
    for group in groups:
        for row in group or []:
            row_id = row.get("id")
            if row_id and row_id not in by_id:
                by_id[row_id] = row
    return list(by_id.values())


def _locale_by_id(locale_id: int) -> dict:
    for locale in META_LOCALES:
        if locale["id"] == locale_id:
            return locale
    raise HTTPException(status_code=400, detail="Locale ID not supported")


def _media_or_404(media_id: str) -> dict:
    doc = fb_media_assets_col.find_one({"_id": oid(media_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Media asset not found")
    return doc


def _download_public_url(url: str, media_type: str) -> str:
    suffix = os.path.splitext(urlparse(url).path)[1].lower() or (".mp4" if media_type == "video" else ".jpg")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = tmp.name
        try:
            with requests.get(url, stream=True, timeout=300) as res:
                res.raise_for_status()
                for chunk in res.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        tmp.write(chunk)
        except Exception as exc:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise HTTPException(status_code=400, detail=f"No se pudo descargar la URL: {exc}")
    return tmp_path


def _upload_image(act_id: str, token: str, path: str) -> str:
    with open(path, "rb") as file:
        res = requests.post(f"{GRAPH}/{act_id}/adimages", data={"access_token": token}, files={"filename1": file}, timeout=300)
    payload = res.json()
    if res.status_code >= 400 or payload.get("error"):
        err = payload.get("error", {})
        raise HTTPException(status_code=400, detail=err.get("error_user_msg") or err.get("message") or payload)
    for item in payload.get("images", {}).values():
        if item.get("hash"):
            return item["hash"]
    raise HTTPException(status_code=400, detail="Meta did not return image hash")


def _upload_video(act_id: str, token: str, path: str, title: str) -> str:
    file_size = os.path.getsize(path)
    if file_size < 50 * 1024 * 1024:
        with open(path, "rb") as file:
            res = requests.post(f"{GRAPH}/{act_id}/advideos", data={"access_token": token, "title": title}, files={"source": file}, timeout=600)
        payload = res.json()
        if res.status_code >= 400 or payload.get("error"):
            err = payload.get("error", {})
            raise HTTPException(status_code=400, detail=err.get("error_user_msg") or err.get("message") or payload)
        if payload.get("id"):
            return payload["id"]
        raise HTTPException(status_code=400, detail="Meta did not return video id")

    start = requests.post(
        f"{GRAPH}/{act_id}/advideos",
        data={"upload_phase": "start", "file_size": str(file_size), "access_token": token},
        timeout=60,
    ).json()
    upload_session_id = start.get("upload_session_id")
    video_id = start.get("video_id")
    if not upload_session_id or not video_id:
        raise HTTPException(status_code=400, detail=start.get("error", {}).get("message") or "Meta video upload start failed")

    start_offset = int(start.get("start_offset", 0))
    end_offset = int(start.get("end_offset", 10 * 1024 * 1024))
    with open(path, "rb") as file:
        while start_offset < file_size:
            file.seek(start_offset)
            chunk = file.read(end_offset - start_offset)
            transfer = requests.post(
                f"{GRAPH}/{act_id}/advideos",
                data={"upload_phase": "transfer", "upload_session_id": upload_session_id, "start_offset": str(start_offset), "access_token": token},
                files={"video_file_chunk": ("chunk", chunk)},
                timeout=180,
            ).json()
            if transfer.get("error"):
                raise HTTPException(status_code=400, detail=transfer["error"].get("message"))
            start_offset = int(transfer.get("start_offset", file_size))
            end_offset = int(transfer.get("end_offset", file_size))

    finish = requests.post(
        f"{GRAPH}/{act_id}/advideos",
        data={"upload_phase": "finish", "upload_session_id": upload_session_id, "title": title, "access_token": token},
        timeout=60,
    ).json()
    if not finish.get("success"):
        raise HTTPException(status_code=400, detail=finish.get("error", {}).get("message") or "Meta video upload finish failed")
    return video_id


def _catalog_or_404(catalog_id: str) -> dict:
    doc = fb_catalogs_col.find_one({"_id": oid(catalog_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Catalog not found")
    return doc


def _public_base(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _build_set_name(products: list[dict]) -> str:
    labels = [p.get("video_label") for p in products if p.get("video_label")]
    if not labels:
        return "+".join([p.get("retailer_id", "") for p in products if p.get("retailer_id")]) or "Product Set"
    base_parts = labels[0].split("_")
    base = "_".join(base_parts[:2]) if len(base_parts) >= 3 else ""
    versions = [(label.split("_")[-1] if len(label.split("_")) >= 3 else label) for label in labels]
    return f"{base}_{'+'.join(versions)}" if base else "+".join(versions)


def _defaults_for_campaign(payload: CampaignBase) -> tuple[dict, str, str, str, str]:
    cfg = _get_config(payload.configId)
    token = _token_for_config(payload.configId)
    act = (payload.adAccountId or cfg.get("default_ad_account_id") or "").strip()
    page_id = (payload.pageId or cfg.get("default_page_id") or "").strip()
    pixel_id = (payload.pixelId or cfg.get("default_pixel_id") or "").strip()
    if not act or not page_id or not pixel_id:
        raise HTTPException(status_code=400, detail="Ad account, page and pixel are required")
    if not act.startswith("act_"):
        act = f"act_{act}"
    return cfg, token, act, page_id, pixel_id


def _campaign_targeting(countries: str, age_min: int, age_max: int, locale_ids: list[int]) -> str:
    return json.dumps({
        "geo_locations": {"countries": [c.strip().upper() for c in countries.split(",") if c.strip()] or ["US"]},
        "age_min": age_min,
        "age_max": age_max,
        "locales": locale_ids or [6],
        "targeting_automation": {"advantage_audience": 0},
    })


def _page_backed_ig(page_id: str, token: str) -> str | None:
    try:
        pages = _meta_get("me/accounts", token, {"fields": "id,access_token", "limit": 100}).get("data", [])
        page_token = next((page.get("access_token") for page in pages if page.get("id") == page_id), None)
        if not page_token:
            return None
        res = requests.get(f"{GRAPH}/{page_id}/page_backed_instagram_accounts", params={"access_token": page_token}, timeout=30).json()
        for ig in res.get("data", []):
            return ig.get("id")
    except Exception:
        return None
    return None


def _create_campaign_and_adset(payload: CampaignBase, token: str, act: str, pixel_id: str) -> dict:
    campaign_payload = {
        "name": payload.name,
        "objective": payload.objective,
        "status": "PAUSED",
        "buying_type": "AUCTION",
        "special_ad_categories": json.dumps([]),
        "is_adset_budget_sharing_enabled": False,
    }
    if payload.cboOrAbo == "CBO":
        if payload.budgetType == "lifetime":
            campaign_payload["lifetime_budget"] = int(payload.dailyBudgetUsd * 100)
        else:
            campaign_payload["daily_budget"] = int(payload.dailyBudgetUsd * 100)
        campaign_payload["bid_strategy"] = payload.bidStrategy
    if payload.spendCapUsd and payload.spendCapUsd > 0:
        campaign_payload["spend_cap"] = int(payload.spendCapUsd * 100)
    campaign = _meta_post(f"{act}/campaigns", token, campaign_payload)

    adset_payload = {
        "name": payload.adsetName.strip() if payload.adsetName and payload.adsetName.strip() else f"AS-{payload.name}",
        "campaign_id": campaign["id"],
        "billing_event": "IMPRESSIONS",
        "optimization_goal": payload.optimizationGoal,
        "targeting": _campaign_targeting(payload.countries, payload.ageMin, payload.ageMax, payload.localeIds),
        "promoted_object": json.dumps({"pixel_id": pixel_id, "custom_event_type": payload.customEventType}),
        "status": "PAUSED",
    }
    if payload.startTime:
        adset_payload["start_time"] = payload.startTime
    if payload.endTime:
        adset_payload["end_time"] = payload.endTime
    if payload.cboOrAbo == "ABO":
        if payload.budgetType == "lifetime":
            adset_payload["lifetime_budget"] = int(payload.dailyBudgetUsd * 100)
        else:
            adset_payload["daily_budget"] = int(payload.dailyBudgetUsd * 100)
        adset_payload["bid_strategy"] = payload.bidStrategy
    if payload.bidStrategy in ("COST_CAP", "LOWEST_COST_WITH_BID_CAP") and payload.bidAmountUsd > 0:
        adset_payload["bid_amount"] = int(payload.bidAmountUsd * 100)
    if payload.bidStrategy == "LOWEST_COST_WITH_MIN_ROAS" and payload.roasFloor > 0:
        adset_payload["bid_constraints"] = json.dumps({"roas_average_floor": int(payload.roasFloor * 10000)})
    adset = _meta_post(f"{act}/adsets", token, adset_payload)
    return {"campaign_id": campaign["id"], "adset_id": adset["id"]}


def _dof_opt_out() -> str:
    features = [
        "adapt_to_placement", "add_text_overlay", "enhance_cta", "image_brightness_and_contrast",
        "image_touchups", "image_uncrop", "inline_comment", "text_optimizations",
        "description_automation", "image_templates", "image_background_gen", "image_animation",
        "media_type_automation", "product_extensions", "site_extensions", "reveal_details_over_time",
        "creative_stickers", "video_auto_crop", "text_translation", "pac_relaxation",
    ]
    return json.dumps({"creative_features_spec": {feature: {"enroll_status": "OPT_OUT"} for feature in features}})


def _domain(url: str) -> str:
    return urlparse(url).netloc


def _asset_feed_spec(real_media_id: str, default_media_id: str, is_video: bool, bundle: dict, carnadas: list[dict], locale_ids: list[int], cta_type: str) -> str:
    if not carnadas:
        raise HTTPException(status_code=400, detail=f"Copy bundle {bundle.get('name')} has no carnadas")
    real_label = _locale_by_id(bundle.get("target_locale_id") or 6)["code"]
    default_label = carnadas[0]["locale_code"]
    media_key = "videos" if is_video else "images"
    id_key = "video_id" if is_video else "hash"
    label_key = "video_label" if is_video else "image_label"
    media_block = [{"adlabels": [{"name": real_label}], id_key: real_media_id}, {"adlabels": [{"name": default_label}], id_key: default_media_id}]
    bodies, titles, descs, links, rules = [], [], [], [], []
    mid = len(carnadas) // 2
    for index, carnada in enumerate(carnadas):
        if index == mid:
            bodies.append({"adlabels": [{"name": real_label}], "text": bundle.get("real_body", "")})
            titles.append({"adlabels": [{"name": real_label}], "text": bundle.get("real_title", "")})
            descs.append({"adlabels": [{"name": real_label}], "text": bundle.get("real_desc", "")})
            links.append({"adlabels": [{"name": real_label}], "website_url": bundle.get("real_url", ""), "display_url": _domain(bundle.get("real_url", ""))})
            rules.append({"customization_spec": {"age_max": 65, "age_min": 13, "locales": locale_ids or [bundle.get("target_locale_id") or 6]}, label_key: {"name": real_label}, "body_label": {"name": real_label}, "description_label": {"name": real_label}, "link_url_label": {"name": real_label}, "title_label": {"name": real_label}, "is_default": False})
        label = carnada["locale_code"]
        bodies.append({"adlabels": [{"name": label}], "text": carnada.get("body", "")})
        titles.append({"adlabels": [{"name": label}], "text": carnada.get("title", "")})
        descs.append({"adlabels": [{"name": label}], "text": carnada.get("description", "")})
        links.append({"adlabels": [{"name": label}], "website_url": carnada.get("url", ""), "display_url": _domain(carnada.get("url", ""))})
        rules.append({"customization_spec": {"age_max": 65, "age_min": 13, "locales": [carnada.get("locale_id")]}, label_key: {"name": default_label}, "body_label": {"name": label}, "description_label": {"name": label}, "link_url_label": {"name": label}, "title_label": {"name": label}, "is_default": index == 0})
    return json.dumps({media_key: media_block, "bodies": bodies, "titles": titles, "descriptions": descs, "link_urls": links, "call_to_action_types": [cta_type], "ad_formats": ["SINGLE_VIDEO" if is_video else "SINGLE_IMAGE"], "optimization_type": "LANGUAGE", "asset_customization_rules": rules})


@router.get("/summary")
def summary(configId: str | None = Query(default=None)):
    query = {"config_id": configId} if configId else {}
    catalog_ids = [str(doc["_id"]) for doc in fb_catalogs_col.find(query, {"_id": 1})]
    product_query = {"catalog_id": {"$in": catalog_ids}} if catalog_ids else ({"catalog_id": "__none__"} if configId else {})
    return {
        "catalogs": fb_catalogs_col.count_documents(query),
        "products": fb_products_col.count_documents(product_query),
        "sets": fb_product_sets_col.count_documents(product_query),
        "campaigns": fb_campaigns_col.count_documents(query),
        "templates": fb_campaign_templates_col.count_documents(query),
        "pendingTrick": fb_campaigns_col.count_documents({**query, "trick_enabled": True, "trick_executed": {"$ne": True}}),
    }


@router.get("/locales")
def list_locales():
    return META_LOCALES


@router.get("/setup/options")
def setup_options(configId: str, adAccountId: str | None = Query(default=None), businessId: str | None = Query(default=None)):
    cfg = _get_config(configId)
    token = cfg.get("access_token")
    out = {
        "config": {
            **serialize_doc(cfg),
            "access_token": None,
            "tokenConfigured": bool(token),
        },
        "businesses": [],
        "accounts": [],
        "pages": [],
        "pixels": [],
    }
    if not token:
        return out
    selected_business_id = (businessId or cfg.get("default_business_id") or cfg.get("bm_id") or "").strip()
    out["businesses"] = _meta_get_safe("me/businesses", token, {"fields": "id,name", "limit": 100}).get("data", [])

    if selected_business_id:
        owned_accounts = _meta_get_safe(f"{selected_business_id}/owned_ad_accounts", token, {"fields": "id,name,account_id,business,currency,timezone_name", "limit": 200}).get("data", [])
        client_accounts = _meta_get_safe(f"{selected_business_id}/client_ad_accounts", token, {"fields": "id,name,account_id,business,currency,timezone_name", "limit": 200}).get("data", [])
        out["accounts"] = _merge_meta_rows(owned_accounts, client_accounts)
        for account in out["accounts"]:
            account.setdefault("business", {"id": selected_business_id, "name": "BM seleccionado"})

        owned_pages = _meta_get_safe(f"{selected_business_id}/owned_pages", token, {"fields": "id,name,instagram_business_account", "limit": 200}).get("data", [])
        client_pages = _meta_get_safe(f"{selected_business_id}/client_pages", token, {"fields": "id,name,instagram_business_account", "limit": 200}).get("data", [])
        out["pages"] = _merge_meta_rows(owned_pages, client_pages)

    if not out["accounts"]:
        out["accounts"] = _meta_get("me/adaccounts", token, {"fields": "id,name,account_id,business,currency,timezone_name", "limit": 100}).get("data", [])
    if not out["pages"]:
        out["pages"] = _meta_get("me/accounts", token, {"fields": "id,name,instagram_business_account", "limit": 100}).get("data", [])

    business_by_id = {b.get("id"): b for b in out["businesses"] if b.get("id")}
    for account in out["accounts"]:
        business = account.get("business") or {}
        if business.get("id") and business.get("id") not in business_by_id:
            business_by_id[business["id"]] = {"id": business["id"], "name": business.get("name") or "BM de cuenta"}
    if selected_business_id and selected_business_id not in business_by_id:
        business_by_id[selected_business_id] = {"id": selected_business_id, "name": "BM seleccionado"}
    out["businesses"] = list(business_by_id.values())
    selected_act = adAccountId or cfg.get("default_ad_account_id") or (out["accounts"][0].get("id") if out["accounts"] else "")
    if selected_act:
        try:
            out["pixels"] = _meta_get(f"act_{selected_act.replace('act_', '')}/adspixels", token, {"fields": "id,name,last_fired_time", "limit": 50}).get("data", [])
        except HTTPException:
            out["pixels"] = []
    if not out["pixels"] and selected_business_id:
        out["pixels"] = _merge_meta_rows(
            _meta_get_safe(f"{selected_business_id}/owned_pixels", token, {"fields": "id,name,last_fired_time", "limit": 100}).get("data", []),
            _meta_get_safe(f"{selected_business_id}/client_pixels", token, {"fields": "id,name,last_fired_time", "limit": 100}).get("data", []),
        )
    return out


@router.put("/setup/{config_id}")
def save_setup_defaults(config_id: str, payload: SetupDefaultsUpdate):
    _get_config(config_id)
    updates = {
        "bm_id": payload.businessId or "",
        "default_business_id": payload.businessId or "",
        "default_ad_account_id": payload.adAccountId or "",
        "default_page_id": payload.pageId or "",
        "default_pixel_id": payload.pixelId or "",
        "telegram_bot_token": payload.telegramBotToken or "",
        "telegram_chat_id": payload.telegramChatId or "",
        "slack_webhook_url": payload.slackWebhookUrl or "",
        "notify_on_approval": payload.notifyOnApproval,
        "notify_on_conversion": payload.notifyOnConversion,
        "updated_at": now_iso(),
    }
    configs_col.update_one({"_id": oid(config_id)}, {"$set": updates})
    doc = configs_col.find_one({"_id": oid(config_id)})
    public = serialize_doc(doc)
    public.pop("access_token", None)
    public["tokenConfigured"] = bool(doc.get("access_token"))
    return public


@router.post("/setup/{config_id}/test-notification")
def test_setup_notification(config_id: str):
    cfg = _get_config(config_id)
    return notify_fb_catalog(cfg, "Test desde FB Catalog Dashboard - si ves esto, las notificaciones funcionan.")


@router.get("/media")
def list_media(configId: str | None = Query(default=None)):
    query = {"config_id": configId} if configId else {}
    return [serialize_doc(doc) for doc in fb_media_assets_col.find(query).sort("created_at", -1)]


@router.post("/media")
def create_media(payload: MediaAssetPayload):
    doc = {
        "config_id": payload.configId,
        "name": payload.name.strip(),
        "type": payload.type,
        "public_url": payload.publicUrl.strip(),
        "notes": payload.notes or "",
        "is_default": payload.isDefault,
        "uploaded_to_meta": False,
        "meta_id": None,
        "ad_account_id": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    res = fb_media_assets_col.insert_one(doc)
    return serialize_doc({**doc, "_id": res.inserted_id})


@router.put("/media/{media_id}")
def update_media(media_id: str, payload: MediaAssetPayload):
    current = _media_or_404(media_id)
    url_changed = current.get("public_url") != payload.publicUrl.strip()
    type_changed = current.get("type") != payload.type
    updates = {
        "config_id": payload.configId,
        "name": payload.name.strip(),
        "type": payload.type,
        "public_url": payload.publicUrl.strip(),
        "notes": payload.notes or "",
        "is_default": payload.isDefault,
        "updated_at": now_iso(),
    }
    if (url_changed or type_changed) and current.get("uploaded_to_meta"):
        updates.update({"uploaded_to_meta": False, "meta_id": None})
    fb_media_assets_col.update_one({"_id": oid(media_id)}, {"$set": updates})
    return serialize_doc(fb_media_assets_col.find_one({"_id": oid(media_id)}))


@router.delete("/media/{media_id}")
def delete_media(media_id: str):
    fb_media_assets_col.delete_one({"_id": oid(media_id)})
    return {"ok": True}


@router.post("/media/bulk-delete")
def bulk_delete_media(payload: BulkIdsPayload):
    ids = [oid(item) for item in payload.ids if item]
    if ids:
        fb_media_assets_col.delete_many({"_id": {"$in": ids}})
    return {"ok": True, "deleted": len(ids)}


@router.post("/media/{media_id}/upload")
def upload_media(media_id: str, payload: MediaUploadRequest):
    media = _media_or_404(media_id)
    config_id = payload.configId or media.get("config_id")
    token = _token_for_config(config_id)
    cfg = _get_config(config_id)
    act = (payload.adAccountId or media.get("ad_account_id") or (cfg or {}).get("default_ad_account_id") or "").strip()
    if not act:
        raise HTTPException(status_code=400, detail="Ad account is required")
    if not act.startswith("act_"):
        act = f"act_{act}"
    path = _download_public_url(media.get("public_url"), media.get("type", "image"))
    try:
        meta_id = _upload_video(act, token, path, media.get("name") or "video") if media.get("type") == "video" else _upload_image(act, token, path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    updates = {"meta_id": meta_id, "ad_account_id": act, "uploaded_to_meta": True, "updated_at": now_iso()}
    fb_media_assets_col.update_one({"_id": oid(media_id)}, {"$set": updates})
    return serialize_doc(fb_media_assets_col.find_one({"_id": oid(media_id)}))


@router.get("/carnadas")
def list_carnadas(configId: str | None = Query(default=None)):
    query = {"config_id": configId} if configId else {}
    return [serialize_doc(doc) for doc in fb_language_carnadas_col.find(query).sort("created_at", -1)]


@router.post("/carnadas")
def create_carnada(payload: CarnadaPayload):
    locale = _locale_by_id(payload.localeId)
    doc = {
        "config_id": payload.configId,
        "locale_id": locale["id"],
        "locale_code": locale["code"],
        "language_name": locale["name"],
        "body": payload.body,
        "title": payload.title,
        "description": payload.description or "",
        "url": payload.url,
        "notes": payload.notes or "",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    res = fb_language_carnadas_col.insert_one(doc)
    return serialize_doc({**doc, "_id": res.inserted_id})


@router.put("/carnadas/{carnada_id}")
def update_carnada(carnada_id: str, payload: CarnadaPayload):
    locale = _locale_by_id(payload.localeId)
    updates = {
        "config_id": payload.configId,
        "locale_id": locale["id"],
        "locale_code": locale["code"],
        "language_name": locale["name"],
        "body": payload.body,
        "title": payload.title,
        "description": payload.description or "",
        "url": payload.url,
        "notes": payload.notes or "",
        "updated_at": now_iso(),
    }
    fb_language_carnadas_col.update_one({"_id": oid(carnada_id)}, {"$set": updates})
    return serialize_doc(fb_language_carnadas_col.find_one({"_id": oid(carnada_id)}))


@router.delete("/carnadas/{carnada_id}")
def delete_carnada(carnada_id: str):
    fb_language_carnadas_col.delete_one({"_id": oid(carnada_id)})
    fb_copy_bundles_col.update_many({}, {"$pull": {"carnada_ids": carnada_id}})
    return {"ok": True}


@router.post("/carnadas/bulk-delete")
def bulk_delete_carnadas(payload: BulkIdsPayload):
    ids = [oid(item) for item in payload.ids if item]
    if ids:
        fb_language_carnadas_col.delete_many({"_id": {"$in": ids}})
        fb_copy_bundles_col.update_many({}, {"$pull": {"carnada_ids": {"$in": payload.ids}}})
    return {"ok": True, "deleted": len(ids)}


@router.get("/copies")
def list_copies(configId: str | None = Query(default=None)):
    query = {"config_id": configId} if configId else {}
    return [serialize_doc(doc) for doc in fb_copy_bundles_col.find(query).sort("created_at", -1)]


@router.post("/copies")
def create_copy(payload: CopyBundlePayload):
    locale = _locale_by_id(payload.targetLocaleId)
    doc = {
        "config_id": payload.configId,
        "name": payload.name.strip(),
        "real_body": payload.realBody,
        "real_title": payload.realTitle,
        "real_desc": payload.realDesc,
        "real_url": payload.realUrl,
        "target_locale_id": locale["id"],
        "target_locale_code": locale["code"],
        "carnada_ids": payload.carnadaIds,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    res = fb_copy_bundles_col.insert_one(doc)
    return serialize_doc({**doc, "_id": res.inserted_id})


@router.put("/copies/{copy_id}")
def update_copy(copy_id: str, payload: CopyBundlePayload):
    locale = _locale_by_id(payload.targetLocaleId)
    updates = {
        "config_id": payload.configId,
        "name": payload.name.strip(),
        "real_body": payload.realBody,
        "real_title": payload.realTitle,
        "real_desc": payload.realDesc,
        "real_url": payload.realUrl,
        "target_locale_id": locale["id"],
        "target_locale_code": locale["code"],
        "carnada_ids": payload.carnadaIds,
        "updated_at": now_iso(),
    }
    fb_copy_bundles_col.update_one({"_id": oid(copy_id)}, {"$set": updates})
    return serialize_doc(fb_copy_bundles_col.find_one({"_id": oid(copy_id)}))


@router.delete("/copies/{copy_id}")
def delete_copy(copy_id: str):
    fb_copy_bundles_col.delete_one({"_id": oid(copy_id)})
    return {"ok": True}


@router.get("/catalogs")
def list_catalogs(request: Request, configId: str | None = Query(default=None)):
    query = {"config_id": configId} if configId else {}
    docs = list(fb_catalogs_col.find(query).sort("created_at", -1))
    base = _public_base(request)
    return [{**serialize_doc(doc), "feedUrl": f"{base}/feed/{doc.get('feed_slug')}.csv"} for doc in docs]


@router.post("/catalogs")
def create_catalog(payload: CatalogCreate, request: Request):
    cfg = _get_config(payload.configId)
    business_id = (payload.businessId or (cfg or {}).get("bm_id") or "").strip()
    if payload.syncToMeta and not business_id:
        raise HTTPException(status_code=400, detail="Business Manager is required to sync with Meta")

    feed_slug = secrets.token_urlsafe(8)
    fb_catalog_id = f"local-{feed_slug}"
    fb_feed_id = None
    if payload.syncToMeta:
        token = _token_for_config(payload.configId)
        catalog_res = _meta_post(f"{business_id}/owned_product_catalogs", token, {"name": payload.name, "vertical": "commerce"})
        fb_catalog_id = catalog_res["id"]
        if payload.pixelId:
            _meta_post(f"{fb_catalog_id}/external_event_sources", token, {"external_event_sources": f'["{payload.pixelId}"]'})
        feed_res = _meta_post(
            f"{fb_catalog_id}/product_feeds",
            token,
            {"name": f"Feed {payload.name}", "schedule": f'{{"interval":"DAILY","url":"{_public_base(request)}/feed/{feed_slug}.csv","hour":4}}'},
        )
        fb_feed_id = feed_res.get("id")

    doc = {
        "config_id": payload.configId,
        "name": payload.name.strip(),
        "business_id": business_id or None,
        "fb_catalog_id": fb_catalog_id,
        "fb_feed_id": fb_feed_id,
        "feed_slug": feed_slug,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    res = fb_catalogs_col.insert_one(doc)
    return serialize_doc({**doc, "_id": res.inserted_id, "feedUrl": f"{_public_base(request)}/feed/{feed_slug}.csv"})


@router.delete("/catalogs/{catalog_id}")
def delete_catalog(catalog_id: str):
    _catalog_or_404(catalog_id)
    fb_catalogs_col.delete_one({"_id": oid(catalog_id)})
    fb_products_col.delete_many({"catalog_id": catalog_id})
    fb_product_sets_col.delete_many({"catalog_id": catalog_id})
    return {"ok": True}


@router.get("/catalogs/{catalog_id}/products")
def list_products(catalog_id: str):
    catalog = _catalog_or_404(catalog_id)
    rows = [serialize_doc(doc) for doc in fb_products_col.find({"catalog_id": catalog_id}).sort("created_at", 1)]
    return {"catalog": serialize_doc(catalog), "products": rows}


@router.put("/catalogs/{catalog_id}/products/bulk")
def bulk_save_products(catalog_id: str, payload: ProductsBulkSave):
    _catalog_or_404(catalog_id)
    saved = []
    for row in payload.rows:
        if not row.retailerId.strip() or not row.title.strip() or not row.link.strip() or not row.imageLink.strip():
            continue
        data = {
            "catalog_id": catalog_id,
            "retailer_id": row.retailerId.strip(),
            "title": row.title.strip(),
            "description": row.description,
            "availability": row.availability or "in stock",
            "condition": "new",
            "price": row.price or "10.00 USD",
            "link": row.link.strip(),
            "image_link": row.imageLink.strip(),
            "brand": row.brand or "Brand",
            "video_url": row.videoUrl or "",
            "video_label": row.videoLabel or "",
            "tag": row.tag if row.tag in ("clean", "dirty") else "dirty",
            "updated_at": now_iso(),
        }
        if row.id:
            fb_products_col.update_one({"_id": oid(row.id), "catalog_id": catalog_id}, {"$set": data})
            saved_doc = fb_products_col.find_one({"_id": oid(row.id)})
        else:
            data["created_at"] = now_iso()
            res = fb_products_col.insert_one(data)
            saved_doc = fb_products_col.find_one({"_id": res.inserted_id})
        saved.append(serialize_doc(saved_doc))
    return {"ok": True, "products": saved}


@router.delete("/catalogs/{catalog_id}/products/{product_id}")
def delete_product(catalog_id: str, product_id: str):
    fb_products_col.delete_one({"_id": oid(product_id), "catalog_id": catalog_id})
    return {"ok": True}


@router.get("/catalogs/{catalog_id}/sets")
def list_sets(catalog_id: str):
    catalog = _catalog_or_404(catalog_id)
    products = [serialize_doc(doc) for doc in fb_products_col.find({"catalog_id": catalog_id}).sort("created_at", 1)]
    sets = [serialize_doc(doc) for doc in fb_product_sets_col.find({"catalog_id": catalog_id}).sort("created_at", -1)]
    return {"catalog": serialize_doc(catalog), "sets": sets, "products": products}


@router.get("/sets/all")
def list_all_sets(configId: str | None = Query(default=None)):
    catalog_query = {"config_id": configId} if configId else {}
    catalogs = list(fb_catalogs_col.find(catalog_query))
    if not catalogs:
        return []
    catalog_by_id = {str(c["_id"]): c for c in catalogs}
    rows = []
    for doc in fb_product_sets_col.find({"catalog_id": {"$in": list(catalog_by_id.keys())}}).sort("created_at", -1):
        catalog = catalog_by_id.get(doc.get("catalog_id"), {})
        rows.append({
            **serialize_doc(doc),
            "catalog_name": catalog.get("name", ""),
            "catalog_fb_id": catalog.get("fb_catalog_id", ""),
            "synced": bool(doc.get("fb_set_id")),
        })
    return rows


@router.post("/catalogs/{catalog_id}/sets")
def create_set(catalog_id: str, payload: ProductSetCreate):
    catalog = _catalog_or_404(catalog_id)
    if not payload.productIds:
        raise HTTPException(status_code=400, detail="Select at least one product")
    product_oids = [oid(product_id) for product_id in payload.productIds]
    products = list(fb_products_col.find({"catalog_id": catalog_id, "_id": {"$in": product_oids}}))
    if not products:
        raise HTTPException(status_code=400, detail="Products not found")
    name = (payload.name or "").strip() or _build_set_name(products)
    retailer_ids = [p["retailer_id"] for p in products]
    fb_set_id = None
    if payload.syncToMeta:
        if str(catalog.get("fb_catalog_id", "")).startswith("local-"):
            raise HTTPException(status_code=400, detail="Catalog is not synced with Meta")
        token = _token_for_config(payload.configId or catalog.get("config_id"))
        res = _meta_post(f"{catalog['fb_catalog_id']}/product_sets", token, {"name": name, "filter": json.dumps({"retailer_id": {"is_any": retailer_ids}})})
        fb_set_id = res.get("id")
    doc = {
        "catalog_id": catalog_id,
        "name": name,
        "retailer_ids": retailer_ids,
        "product_ids": payload.productIds,
        "fb_set_id": fb_set_id,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    res = fb_product_sets_col.insert_one(doc)
    return serialize_doc({**doc, "_id": res.inserted_id})


@router.delete("/catalogs/{catalog_id}/sets/{set_id}")
def delete_set(catalog_id: str, set_id: str):
    fb_product_sets_col.delete_one({"_id": oid(set_id), "catalog_id": catalog_id})
    return {"ok": True}


@router.get("/campaigns")
def list_campaigns(configId: str | None = Query(default=None)):
    query = {"config_id": configId} if configId else {}
    return [serialize_doc(doc) for doc in fb_campaigns_col.find(query).sort("created_at", -1).limit(100)]


@router.post("/campaigns/normal")
def create_normal_campaign(payload: NormalCampaignPayload):
    if not payload.ads:
        raise HTTPException(status_code=400, detail="At least one ad is required")
    _cfg, token, act, page_id, pixel_id = _defaults_for_campaign(payload)
    ids = _create_campaign_and_adset(payload, token, act, pixel_id)
    ig_id = payload.instagramId or _page_backed_ig(page_id, token)
    ads_out = []
    errors = []
    for index, ad in enumerate(payload.ads, start=1):
        media = _media_or_404(ad.mediaAssetId)
        if not media.get("uploaded_to_meta") or not media.get("meta_id"):
            errors.append(f"Ad #{index}: creativo '{media.get('name')}' no esta subido a Meta")
            continue
        link_data = {"link": ad.link, "message": ad.body, "name": ad.title, "call_to_action": {"type": ad.ctaType, "value": {"link": ad.link}}}
        if ad.description:
            link_data["description"] = ad.description
        if media.get("type") == "video":
            link_data["video_id"] = media["meta_id"]
            story_spec = {"page_id": page_id, "video_data": link_data}
        else:
            link_data["image_hash"] = media["meta_id"]
            story_spec = {"page_id": page_id, "link_data": link_data}
        if ig_id:
            story_spec["instagram_user_id"] = ig_id
        creative = _meta_post(f"{act}/adcreatives", token, {"name": f"CR-{ad.adName}" if ad.adName else f"CR-{payload.name}-{index}", "object_story_spec": json.dumps(story_spec), "is_multi_advertiser_ads_opted_in": False, **({"url_tags": payload.urlTags} if payload.urlTags else {})})
        created_ad = _meta_post(f"{act}/ads", token, {"name": ad.adName or f"AD-{payload.name}-{index}", "adset_id": ids["adset_id"], "creative": json.dumps({"creative_id": creative["id"]}), "status": "PAUSED"})
        ads_out.append({"index": index, "creative_id": creative["id"], "ad_id": created_ad["id"], "media_asset_id": ad.mediaAssetId})
    doc = {"config_id": payload.configId, "campaign_type": "normal", "name": payload.name, "ad_account_id": act.replace("act_", ""), "fb_campaign_id": ids["campaign_id"], "fb_adset_id": ids["adset_id"], "fb_ad_id": ads_out[0]["ad_id"] if ads_out else "", "trick_enabled": payload.trickEnabled, "trick_executed": False, "ads": ads_out, "errors": errors, "payload": payload.model_dump(), "created_at": now_iso(), "updated_at": now_iso()}
    res = fb_campaigns_col.insert_one(doc)
    if errors and not ads_out:
        raise HTTPException(status_code=400, detail={"errors": errors, "campaign": serialize_doc({**doc, "_id": res.inserted_id})})
    return serialize_doc({**doc, "_id": res.inserted_id})


@router.post("/campaigns/language")
def create_language_campaign(payload: LanguageCampaignPayload):
    if not payload.ads:
        raise HTTPException(status_code=400, detail="At least one ad is required")
    _cfg, token, act, page_id, pixel_id = _defaults_for_campaign(payload)
    ids = _create_campaign_and_adset(payload, token, act, pixel_id)
    ig_id = payload.instagramId or _page_backed_ig(page_id, token)
    story_spec = {"page_id": page_id}
    if ig_id:
        story_spec["instagram_user_id"] = ig_id
    ads_out = []
    errors = []
    for index, ad in enumerate(payload.ads, start=1):
        real_media = _media_or_404(ad.mediaAssetId)
        default_media = _media_or_404(ad.defaultMediaId)
        bundle = fb_copy_bundles_col.find_one({"_id": oid(ad.copyBundleId)})
        if not bundle:
            errors.append(f"Ad #{index}: copy bundle no encontrado")
            continue
        if not real_media.get("uploaded_to_meta") or not default_media.get("uploaded_to_meta"):
            errors.append(f"Ad #{index}: creativos no subidos a Meta")
            continue
        carnada_oids = [oid(carnada_id) for carnada_id in bundle.get("carnada_ids", [])]
        carnadas_by_id = {str(doc["_id"]): doc for doc in fb_language_carnadas_col.find({"_id": {"$in": carnada_oids}})}
        carnadas = [carnadas_by_id[carnada_id] for carnada_id in bundle.get("carnada_ids", []) if carnada_id in carnadas_by_id]
        afs = _asset_feed_spec(real_media["meta_id"], default_media["meta_id"], real_media.get("type") == "video", bundle, carnadas, payload.localeIds, ad.ctaType)
        creative = _meta_post(f"{act}/adcreatives", token, {"name": f"CR-{ad.adName}" if ad.adName else f"CR-{payload.name}-{index}", "object_story_spec": json.dumps(story_spec), "asset_feed_spec": afs, "contextual_multi_ads": json.dumps({"enroll_status": "OPT_OUT"}), "degrees_of_freedom_spec": _dof_opt_out(), **({"url_tags": payload.urlTags} if payload.urlTags else {})})
        created_ad = _meta_post(f"{act}/ads", token, {"name": ad.adName or f"AD-{payload.name}-{index}", "adset_id": ids["adset_id"], "creative": json.dumps({"creative_id": creative["id"]}), "status": "PAUSED"})
        ads_out.append({"index": index, "creative_id": creative["id"], "ad_id": created_ad["id"], "media_asset_id": ad.mediaAssetId, "copy_bundle_id": ad.copyBundleId})
    doc = {"config_id": payload.configId, "campaign_type": "language", "name": payload.name, "ad_account_id": act.replace("act_", ""), "fb_campaign_id": ids["campaign_id"], "fb_adset_id": ids["adset_id"], "fb_ad_id": ads_out[0]["ad_id"] if ads_out else "", "trick_enabled": payload.trickEnabled, "trick_executed": False, "ads": ads_out, "errors": errors, "payload": payload.model_dump(), "created_at": now_iso(), "updated_at": now_iso()}
    res = fb_campaigns_col.insert_one(doc)
    if errors and not ads_out:
        raise HTTPException(status_code=400, detail={"errors": errors, "campaign": serialize_doc({**doc, "_id": res.inserted_id})})
    return serialize_doc({**doc, "_id": res.inserted_id})


@router.post("/campaigns/catalog")
def create_catalog_campaign(payload: CatalogCampaignPayload):
    product_set = fb_product_sets_col.find_one({"_id": oid(payload.productSetId)})
    if not product_set:
        raise HTTPException(status_code=404, detail="Product set not found")
    if not product_set.get("fb_set_id"):
        raise HTTPException(status_code=400, detail="Product set must be synced to Meta")

    _cfg, token, act, page_id, pixel_id = _defaults_for_campaign(payload)
    if payload.optimizationGoal in ("OFFSITE_CONVERSIONS", "VALUE") and not pixel_id:
        raise HTTPException(status_code=400, detail="Pixel is required for OFFSITE_CONVERSIONS/VALUE")

    effective_optimization = "VALUE" if payload.bidStrategy == "LOWEST_COST_WITH_MIN_ROAS" else payload.optimizationGoal
    adset_targeting = json.dumps({
        "age_min": payload.ageMin,
        "age_max": payload.ageMax,
        "geo_locations": {"countries": [c.strip().upper() for c in payload.countries.split(",") if c.strip()] or ["US"]},
        **({"locales": payload.localeIds} if payload.localeIds else {}),
        "targeting_automation": {"advantage_audience": 0},
    })

    campaign_payload = {
        "name": payload.name,
        "objective": payload.objective,
        "status": "PAUSED",
        "buying_type": "AUCTION",
        "special_ad_categories": json.dumps([]),
        "is_adset_budget_sharing_enabled": False,
    }
    if payload.cboOrAbo == "CBO":
        if payload.budgetType == "lifetime":
            campaign_payload["lifetime_budget"] = int(payload.dailyBudgetUsd * 100)
        else:
            campaign_payload["daily_budget"] = int(payload.dailyBudgetUsd * 100)
        campaign_payload["bid_strategy"] = payload.bidStrategy
    if payload.spendCapUsd and payload.spendCapUsd > 0:
        campaign_payload["spend_cap"] = int(payload.spendCapUsd * 100)

    campaign = _meta_post(f"{act}/campaigns", token, campaign_payload)

    promoted_object = {"product_set_id": product_set["fb_set_id"]}
    if effective_optimization in ("OFFSITE_CONVERSIONS", "VALUE"):
        promoted_object.update({"pixel_id": pixel_id, "custom_event_type": payload.customEventType})

    adset_payload = {
        "name": payload.adsetName.strip() if payload.adsetName and payload.adsetName.strip() else f"AS-{payload.name}",
        "campaign_id": campaign["id"],
        "billing_event": "IMPRESSIONS",
        "optimization_goal": effective_optimization,
        "promoted_object": json.dumps(promoted_object),
        "targeting": adset_targeting,
        "status": "PAUSED",
    }
    if payload.startTime:
        adset_payload["start_time"] = payload.startTime
    if payload.endTime:
        adset_payload["end_time"] = payload.endTime
    if payload.cboOrAbo == "ABO":
        if payload.budgetType == "lifetime":
            adset_payload["lifetime_budget"] = int(payload.dailyBudgetUsd * 100)
        else:
            adset_payload["daily_budget"] = int(payload.dailyBudgetUsd * 100)
        adset_payload["bid_strategy"] = payload.bidStrategy
    if payload.bidStrategy in ("COST_CAP", "LOWEST_COST_WITH_BID_CAP") and payload.bidAmountUsd > 0:
        adset_payload["bid_amount"] = int(payload.bidAmountUsd * 100)
    if payload.bidStrategy == "LOWEST_COST_WITH_MIN_ROAS" and payload.roasFloor > 0:
        adset_payload["bid_constraints"] = json.dumps({"roas_average_floor": int(payload.roasFloor * 10000)})

    adset = _meta_post(f"{act}/adsets", token, adset_payload)

    ig_id = payload.instagramId or _page_backed_ig(page_id, token)
    td = {
        "link": payload.lander,
        "message": payload.message,
        "name": payload.headline,
        "call_to_action": {"type": payload.ctaType, "value": {"link": payload.lander}},
    }
    if payload.linkDescription:
        td["description"] = payload.linkDescription
    if payload.useVideo:
        td["format_option"] = "single_video"
    story_spec = {"page_id": page_id, "template_data": td}
    if ig_id:
        story_spec["instagram_user_id"] = ig_id

    creative_payload = {
        "name": f"CR-{payload.adName}" if payload.adName else f"CR-{payload.name}",
        "object_story_spec": json.dumps(story_spec),
        "product_set_id": product_set["fb_set_id"],
    }
    if payload.urlTags:
        creative_payload["url_tags"] = payload.urlTags
    if payload.multiAdvertiserOptout:
        creative_payload["is_multi_advertiser_ads_opted_in"] = False

    creative = _meta_post(f"{act}/adcreatives", token, creative_payload)
    ad = _meta_post(f"{act}/ads", token, {"name": payload.adName or f"AD-{payload.name}", "adset_id": adset["id"], "creative": json.dumps({"creative_id": creative["id"]}), "status": "PAUSED"})

    doc = {
        "config_id": payload.configId,
        "campaign_type": "catalog",
        "name": payload.name,
        "ad_account_id": act.replace("act_", ""),
        "catalog_id": product_set.get("catalog_id"),
        "product_set_id": payload.productSetId,
        "fb_campaign_id": campaign["id"],
        "fb_adset_id": adset["id"],
        "fb_creative_id": creative["id"],
        "fb_ad_id": ad["id"],
        "trick_enabled": payload.trickEnabled,
        "trick_executed": False,
        "payload": payload.model_dump(),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    res = fb_campaigns_col.insert_one(doc)
    return serialize_doc({**doc, "_id": res.inserted_id})


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: str):
    fb_campaigns_col.delete_one({"_id": oid(campaign_id)})
    return {"ok": True}


@router.get("/templates")
def list_templates(configId: str | None = Query(default=None)):
    query = {"config_id": configId} if configId else {}
    return [serialize_doc(doc) for doc in fb_campaign_templates_col.find(query).sort("created_at", -1)]


@router.post("/templates")
def create_template(payload: TemplatePayload):
    doc = {"config_id": payload.configId, "name": payload.name.strip(), "campaign_type": payload.campaignType, "config": payload.config, "created_at": now_iso(), "updated_at": now_iso()}
    res = fb_campaign_templates_col.insert_one(doc)
    return serialize_doc({**doc, "_id": res.inserted_id})


@router.delete("/templates/{template_id}")
def delete_template(template_id: str):
    fb_campaign_templates_col.delete_one({"_id": oid(template_id)})
    return {"ok": True}


@router.get("/planning")
def list_planning(configId: str | None = Query(default=None)):
    query = {"config_id": configId} if configId else {}
    return [serialize_doc(doc) for doc in fb_planned_campaigns_col.find(query).sort("created_at", -1)]


@router.post("/planning")
def create_plan(payload: PlannedCampaignPayload):
    doc = {"config_id": payload.configId, "campaign_type": payload.campaignType, "name": payload.name.strip(), "config": payload.config, "scheduled_at": payload.scheduledAt or "", "status": "pending", "result_ids": {}, "error_msg": "", "created_at": now_iso(), "updated_at": now_iso()}
    res = fb_planned_campaigns_col.insert_one(doc)
    return serialize_doc({**doc, "_id": res.inserted_id})


@router.put("/planning/{plan_id}")
def update_plan(plan_id: str, payload: PlannedCampaignPayload):
    updates = {"config_id": payload.configId, "campaign_type": payload.campaignType, "name": payload.name.strip(), "config": payload.config, "scheduled_at": payload.scheduledAt or "", "status": "pending", "error_msg": "", "updated_at": now_iso()}
    fb_planned_campaigns_col.update_one({"_id": oid(plan_id)}, {"$set": updates})
    return serialize_doc(fb_planned_campaigns_col.find_one({"_id": oid(plan_id)}))


@router.post("/planning/{plan_id}/duplicate")
def duplicate_plan(plan_id: str):
    plan = fb_planned_campaigns_col.find_one({"_id": oid(plan_id)})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    clone = {k: v for k, v in plan.items() if k != "_id"}
    clone["name"] = f"{clone.get('name', 'Plan')} (copia)"
    clone["status"] = "pending"
    clone["result_ids"] = {}
    clone["error_msg"] = ""
    clone["scheduled_at"] = ""
    clone["created_at"] = now_iso()
    clone["updated_at"] = now_iso()
    res = fb_planned_campaigns_col.insert_one(clone)
    return serialize_doc({**clone, "_id": res.inserted_id})


@router.delete("/planning/{plan_id}")
def delete_plan(plan_id: str):
    fb_planned_campaigns_col.delete_one({"_id": oid(plan_id)})
    return {"ok": True}


@router.post("/planning/bulk-delete")
def bulk_delete_plans(payload: BulkIdsPayload):
    ids = [oid(item) for item in payload.ids if item]
    if ids:
        fb_planned_campaigns_col.delete_many({"_id": {"$in": ids}})
    return {"ok": True, "deleted": len(ids)}


def _execute_plan_doc(plan: dict) -> dict:
    fb_planned_campaigns_col.update_one({"_id": plan["_id"]}, {"$set": {"status": "executing", "updated_at": now_iso()}})
    try:
        config = dict(plan.get("config") or {})
        config["configId"] = plan.get("config_id")
        config["name"] = config.get("name") or plan.get("name")
        if plan.get("campaign_type") == "normal":
            result = create_normal_campaign(NormalCampaignPayload(**config))
        elif plan.get("campaign_type") == "language":
            result = create_language_campaign(LanguageCampaignPayload(**config))
        elif plan.get("campaign_type") == "catalog":
            result = create_catalog_campaign(CatalogCampaignPayload(**config))
        else:
            raise HTTPException(status_code=400, detail="Unsupported plan type")
        fb_planned_campaigns_col.update_one({"_id": plan["_id"]}, {"$set": {"status": "done", "result_ids": result, "error_msg": "", "executed_at": now_iso(), "updated_at": now_iso()}})
        cfg = _get_config(plan.get("config_id"))
        if cfg and cfg.get("notify_on_approval"):
            notify_fb_catalog(cfg, f"FB Catalog plan ejecutado: {plan.get('name')}\nCampaign ID: {result.get('fb_campaign_id', '-')}")
        return {"ok": True, "result": result}
    except Exception as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        fb_planned_campaigns_col.update_one({"_id": plan["_id"]}, {"$set": {"status": "error", "error_msg": str(detail), "updated_at": now_iso()}})
        try:
            cfg = _get_config(plan.get("config_id"))
            notify_fb_catalog(cfg, f"Error ejecutando plan FB Catalog: {plan.get('name')}\n{detail}")
        except Exception:
            pass
        return {"ok": False, "error": detail}


@router.post("/planning/{plan_id}/execute")
def execute_plan(plan_id: str):
    plan = fb_planned_campaigns_col.find_one({"_id": oid(plan_id)})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    result = _execute_plan_doc(plan)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/planning/execute-pending")
def execute_pending(configId: str):
    plans = list(fb_planned_campaigns_col.find({"config_id": configId, "status": {"$in": ["pending", "error"]}}).sort("created_at", 1))
    return {"results": [_execute_plan_doc(plan) for plan in plans]}


@router.post("/planning/execute-due")
def execute_due_plans(configId: str | None = None):
    due_filter = {"status": "pending", "scheduled_at": {"$ne": "", "$lte": now_iso()}}
    if configId:
        due_filter["config_id"] = configId
    plans = list(fb_planned_campaigns_col.find(due_filter).sort("scheduled_at", 1).limit(20))
    return {"results": [_execute_plan_doc(plan) for plan in plans]}


@router.get("/trick")
def trick_status(configId: str | None = Query(default=None)):
    query = {"config_id": configId, "trick_enabled": True} if configId else {"trick_enabled": True}
    pending = [serialize_doc(doc) for doc in fb_campaigns_col.find({**query, "trick_executed": {"$ne": True}}).sort("created_at", -1)]
    done = [serialize_doc(doc) for doc in fb_campaigns_col.find({**query, "trick_executed": True}).sort("trick_executed_at", -1)]
    return {"pending": pending, "done": done}


@router.post("/trick/run-now")
def trick_run_now(configId: str | None = None):
    query = {"config_id": configId, "trick_enabled": True, "trick_executed": {"$ne": True}} if configId else {"trick_enabled": True, "trick_executed": {"$ne": True}}
    updated = 0
    for camp in fb_campaigns_col.find(query):
        if not camp.get("fb_ad_id"):
            continue
        try:
            token = _token_for_config(camp.get("config_id"))
            ad = _meta_get(camp["fb_ad_id"], token, {"fields": "id,effective_status"})
            updates = {"last_status": ad.get("effective_status"), "updated_at": now_iso()}
            if ad.get("effective_status") == "ACTIVE":
                updates.update({"trick_executed": True, "trick_executed_at": now_iso()})
                updated += 1
                cfg = _get_config(camp.get("config_id"))
                if cfg and cfg.get("notify_on_approval"):
                    notify_fb_catalog(cfg, f"Truco automatico ejecutado: {camp.get('name')}\nAd ID: {camp.get('fb_ad_id')} ya esta ACTIVE")
            fb_campaigns_col.update_one({"_id": camp["_id"]}, {"$set": updates})
        except Exception as exc:
            fb_campaigns_col.update_one({"_id": camp["_id"]}, {"$set": {"last_status": f"ERROR: {exc}", "updated_at": now_iso()}})
            try:
                cfg = _get_config(camp.get("config_id"))
                notify_fb_catalog(cfg, f"Error revisando truco automatico: {camp.get('name')}\n{exc}")
            except Exception:
                pass
    return {"ok": True, "updated": updated}


def _feed_response(slug: str) -> Response:
    catalog = fb_catalogs_col.find_one({"feed_slug": slug})
    if not catalog:
        raise HTTPException(status_code=404, detail="Feed not found")
    products = fb_products_col.find({"catalog_id": str(catalog["_id"])})
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(FEED_COLS)
    for product in products:
        writer.writerow([
            product.get("retailer_id", ""),
            product.get("title", ""),
            product.get("description", ""),
            product.get("availability", "in stock"),
            product.get("condition", "new"),
            product.get("price", "10.00 USD"),
            product.get("link", ""),
            product.get("image_link", ""),
            product.get("brand", "Brand"),
            product.get("video_url", ""),
        ])
    return Response(content=buf.getvalue(), media_type="text/csv; charset=utf-8")


@router.get("/feed/{slug}.csv")
def api_feed(slug: str):
    return _feed_response(slug)


@public_router.get("/feed/{slug}.csv", include_in_schema=False)
def public_feed(slug: str):
    return _feed_response(slug)
