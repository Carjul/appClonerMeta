"""
Rutas del truco de idiomas (rediseñado):
  /media        — creativos (URL pública + opcional subida a Meta)
  /carnadas     — biblioteca global de carnadas por idioma
  /copies       — paquetes de copy (real + qué carnadas usar)
  /campaigns/language-trick — crear campaña con el truco
"""
import os
import tempfile
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from typing import Any as Session

from ..database import get_db
from ..meta_connections import get_active_token, get_effective_defaults
from ..models import Campaign
from ..services.language_models import MediaAsset, CopyBundle, LanguageCarnada
from ..services.meta_locales import META_LOCALES, locale_by_id
from ..services.language_trick import (
    upload_image, upload_video,
    create_language_trick_campaign,
)

router = APIRouter()


def _first_ad_result(result: dict):
    ads = result.get("ads") or []
    return ads[0] if ads else {}


def _save_created_campaign(db: Session, *, name: str, ad_account_id: str, campaign_type: str, result: dict, config: dict):
    first_ad = _first_ad_result(result)
    campaign = Campaign(
        fb_campaign_id=result.get("campaign_id"),
        fb_adset_id=result.get("adset_id"),
        fb_creative_id=result.get("creative_id") or first_ad.get("creative_id"),
        fb_ad_id=result.get("ad_id") or first_ad.get("ad_id"),
        name=name,
        ad_account_id=ad_account_id.replace("act_", ""),
        config=config,
        campaign_type=campaign_type,
    )
    db.add(campaign)
    db.commit()
    return campaign


def _format_campaign_errors(result: dict | None = None, fallback: str | None = None):
    errors = [str(err) for err in (result or {}).get("errors", []) if str(err).strip()]
    if not errors and fallback:
        errors = [fallback]
    message = errors[0] if errors else (fallback or "No se pudo crear la campaña.")

    created_bits = []
    if result and result.get("campaign_id"):
        created_bits.append(f"campaign_id: {result['campaign_id']}")
    if result and result.get("adset_id"):
        created_bits.append(f"adset_id: {result['adset_id']}")
    if created_bits:
        message = f"{message} ({', '.join(created_bits)})"
    return message, errors


def _load_campaign_wizard_common(db: Session, selected_ad_account_id: str | None = None):
    from .. import meta_api
    from ..models import AppSettings

    settings = db.query(AppSettings).first()
    if not settings:
        settings = AppSettings()
        db.add(settings)
        db.commit()
    defaults = get_effective_defaults(db)
    for key, value in defaults.items():
        setattr(settings, f"default_{key}", value)

    accounts, pages, pixels = [], [], []
    try:
        token = get_active_token(db)
        accounts = meta_api.list_ad_accounts(token=token)
        pages = meta_api.list_pages(token=token)
        pixel_account_id = selected_ad_account_id or (settings.default_ad_account_id if settings else None)
        if pixel_account_id:
            try:
                pixels = meta_api.list_pixels(pixel_account_id, token=token)
            except Exception:
                pass
    except Exception:
        pass

    bid_strategies = [
        ("LOWEST_COST_WITHOUT_CAP", "Volumen más alto"),
        ("COST_CAP", "Objetivo de costo por resultado"),
        ("LOWEST_COST_WITH_MIN_ROAS", "Objetivo de ROAS"),
        ("LOWEST_COST_WITH_BID_CAP", "Límite de puja"),
    ]
    objectives = [
        ("OUTCOME_SALES", "Ventas"),
        ("OUTCOME_LEADS", "Leads"),
        ("OUTCOME_TRAFFIC", "Tráfico"),
        ("OUTCOME_AWARENESS", "Reconocimiento"),
        ("OUTCOME_ENGAGEMENT", "Interacción"),
    ]
    event_types = [
        ("PURCHASE", "Compra"),
        ("INITIATE_CHECKOUT", "Inicio de checkout"),
        ("ADD_TO_CART", "Añadir al carrito"),
        ("LEAD", "Lead"),
        ("COMPLETE_REGISTRATION", "Registro completo"),
        ("VIEW_CONTENT", "Vista de contenido"),
    ]
    ctas = ["LEARN_MORE", "SHOP_NOW", "SIGN_UP", "SUBSCRIBE", "GET_OFFER", "APPLY_NOW", "DOWNLOAD", "CONTACT_US"]
    return settings, accounts, pages, pixels, bid_strategies, objectives, event_types, ctas


def _render_language_wizard(request: Request, db: Session, *, error: str | None = None,
                            error_details: list[str] | None = None, status_code: int = 200,
                            form: dict | None = None):
    media = db.query(MediaAsset).order_by(MediaAsset.name).all()
    copies = db.query(CopyBundle).order_by(CopyBundle.name).all()
    selected_ad_account_id = (form or {}).get("ad_account_id") if isinstance(form, dict) else None
    settings, accounts, pages, pixels, bid_strategies, objectives, event_types, ctas = _load_campaign_wizard_common(db, selected_ad_account_id)
    optimization_goals = [
        ("OFFSITE_CONVERSIONS", "Conversiones (pixel) — recomendado para Compra/Lead"),
        ("LANDING_PAGE_VIEWS", "Vistas de landing page"),
        ("LINK_CLICKS", "Clics en enlace"),
        ("IMPRESSIONS", "Impresiones"),
        ("REACH", "Alcance"),
        ("LEAD_GENERATION", "Generación de leads (formulario nativo FB)"),
    ]
    return request.app.state.templates.TemplateResponse(request, "campaigns/new_language.html", {
        "request": request, "media": media, "copies": copies,
        "accounts": accounts, "pages": pages, "pixels": pixels,
        "settings": settings, "locales": META_LOCALES,
        "bid_strategies": bid_strategies,
        "objectives": objectives, "event_types": event_types,
        "optimization_goals": optimization_goals, "ctas": ctas,
        "error": error, "error_details": error_details or [],
        "form": form or {},
    }, status_code=status_code)


def _render_normal_wizard(request: Request, db: Session, *, error: str | None = None,
                          error_details: list[str] | None = None, status_code: int = 200,
                          form: dict | None = None):
    media = db.query(MediaAsset).order_by(MediaAsset.name).all()
    selected_ad_account_id = (form or {}).get("ad_account_id") if isinstance(form, dict) else None
    settings, accounts, pages, pixels, bid_strategies, objectives, event_types, ctas = _load_campaign_wizard_common(db, selected_ad_account_id)
    optimization_goals = [
        ("OFFSITE_CONVERSIONS", "Conversiones (pixel) — recomendado para Compra/Lead"),
        ("LANDING_PAGE_VIEWS", "Vistas de landing page"),
        ("LINK_CLICKS", "Clics en enlace"),
        ("IMPRESSIONS", "Impresiones"),
        ("REACH", "Alcance"),
    ]
    return request.app.state.templates.TemplateResponse(request, "campaigns/new_normal.html", {
        "request": request, "media": media,
        "accounts": accounts, "pages": pages, "pixels": pixels,
        "settings": settings, "locales": META_LOCALES,
        "bid_strategies": bid_strategies, "objectives": objectives,
        "event_types": event_types, "optimization_goals": optimization_goals,
        "ctas": ctas,
        "error": error, "error_details": error_details or [],
        "form": form or {},
    }, status_code=status_code)


# ─────────────────────────────────────────────────────────────────
# MEDIA / CREATIVOS (Sheet-style con URL)
# ─────────────────────────────────────────────────────────────────

@router.get("/media")
def list_media(request: Request, db: Session = Depends(get_db)):
    items = db.query(MediaAsset).order_by(MediaAsset.created_at.desc()).all()
    defaults = get_effective_defaults(db)
    return request.app.state.templates.TemplateResponse(request, "media/list.html", {
        "request": request, "items": items, "default_ad_account": defaults["ad_account_id"] or "",
    })


@router.post("/media")
def create_media(
    db: Session = Depends(get_db),
    name: str = Form(...),
    type: str = Form("image"),
    public_url: str = Form(...),
    notes: str = Form(""),
    is_default: str = Form(""),
):
    asset = MediaAsset(
        name=name.strip(),
        type=type if type in ("image", "video") else "image",
        public_url=public_url.strip(),
        notes=notes,
        uploaded_to_meta=False,
        is_default=(is_default == "yes"),
    )
    db.add(asset)
    db.commit()
    return RedirectResponse("/dashboard/media", status_code=303)


@router.post("/media/{media_id}/upload")
def upload_media_to_meta(
    media_id: int,
    db: Session = Depends(get_db),
    ad_account_id: str = Form(""),
):
    """Descarga la URL pública y la sube a Meta. Marca uploaded_to_meta=True."""
    token = get_active_token(db)
    if not token:
        raise HTTPException(400, "No hay conexion Meta activa")

    m = db.query(MediaAsset).filter(MediaAsset.id == media_id).first()
    if not m or not m.public_url:
        raise HTTPException(400, "Creativo no encontrado o sin URL")

    defaults = get_effective_defaults(db)
    act = (ad_account_id or m.ad_account_id or defaults["ad_account_id"] or "").strip()
    if not act:
        raise HTTPException(400, "Configura una cuenta publicitaria en /setup antes de subir creativos a Meta")
    if not act.startswith("act_"):
        act = f"act_{act}"

    suffix = os.path.splitext(urlparse(m.public_url).path)[1].lower() or (".mp4" if m.type == "video" else ".jpg")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        try:
            with requests.get(m.public_url, stream=True, timeout=300) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    tmp.write(chunk)
            tmp_path = tmp.name
        except Exception as e:
            raise HTTPException(400, f"No se pudo descargar la URL: {e}")

    try:
        if m.type == "video":
            meta_id = upload_video(act, token, tmp_path, title=m.name)
        else:
            meta_id = upload_image(act, token, tmp_path)

        if not meta_id:
            raise HTTPException(500, "Upload a Meta falló")

        m.meta_id = meta_id
        m.ad_account_id = act
        m.uploaded_to_meta = True
        db.commit()
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    return RedirectResponse("/dashboard/media", status_code=303)


@router.post("/media/{media_id}/delete")
def delete_media(media_id: int, db: Session = Depends(get_db)):
    m = db.query(MediaAsset).filter(MediaAsset.id == media_id).first()
    if m:
        db.delete(m)
        db.commit()
    return RedirectResponse("/dashboard/media", status_code=303)


@router.post("/media/bulk-delete")
async def bulk_delete_media(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    ids = [int(x) for x in form.getlist("selected_ids") if x.isdigit()]
    if ids:
        db.query(MediaAsset).filter(MediaAsset.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
    return RedirectResponse("/dashboard/media", status_code=303)


@router.get("/media/{media_id}/edit")
def edit_media_form(media_id: int, request: Request, db: Session = Depends(get_db)):
    m = db.query(MediaAsset).filter(MediaAsset.id == media_id).first()
    if not m:
        raise HTTPException(404, "No encontrado")
    return request.app.state.templates.TemplateResponse(request, "media/edit.html", {
        "request": request, "item": m,
    })


@router.post("/media/{media_id}/edit")
def edit_media(
    media_id: int,
    db: Session = Depends(get_db),
    name: str = Form(...),
    type: str = Form("image"),
    public_url: str = Form(...),
    notes: str = Form(""),
    is_default: str = Form(""),
):
    m = db.query(MediaAsset).filter(MediaAsset.id == media_id).first()
    if not m:
        raise HTTPException(404, "No encontrado")

    new_url = public_url.strip()
    new_type = type if type in ("image", "video") else "image"
    # Si la URL o el tipo cambiaron y ya estaba subido a Meta → invalidar
    # para que el usuario pueda volver a subirlo con el nuevo contenido
    url_changed = (m.public_url or "") != new_url
    type_changed = (m.type or "image") != new_type
    if (url_changed or type_changed) and m.uploaded_to_meta:
        m.uploaded_to_meta = False
        m.meta_id = None

    m.name = name.strip()
    m.type = new_type
    m.public_url = new_url
    m.notes = notes
    m.is_default = (is_default == "yes")
    db.commit()
    return RedirectResponse("/dashboard/media", status_code=303)


# ─────────────────────────────────────────────────────────────────
# CARNADAS (biblioteca global por idioma)
# ─────────────────────────────────────────────────────────────────

@router.get("/carnadas")
def list_carnadas(request: Request, db: Session = Depends(get_db)):
    items = db.query(LanguageCarnada).order_by(LanguageCarnada.created_at.desc()).all()
    return request.app.state.templates.TemplateResponse(request, "carnadas/list.html", {
        "request": request, "items": items, "locales": META_LOCALES,
    })


@router.post("/carnadas")
def create_carnada(
    db: Session = Depends(get_db),
    locale_id: int = Form(...),
    body: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    url: str = Form(...),
    notes: str = Form(""),
):
    info = locale_by_id(locale_id)
    if not info:
        raise HTTPException(400, "Locale ID no reconocido")
    c = LanguageCarnada(
        locale_id=locale_id,
        locale_code=info["code"],
        language_name=info["name"],
        body=body, title=title, description=description, url=url, notes=notes,
    )
    db.add(c)
    db.commit()
    return RedirectResponse("/dashboard/carnadas", status_code=303)


@router.post("/carnadas/{carnada_id}/delete")
def delete_carnada(carnada_id: int, db: Session = Depends(get_db)):
    c = db.query(LanguageCarnada).filter(LanguageCarnada.id == carnada_id).first()
    if c:
        db.delete(c)
        db.commit()
    return RedirectResponse("/dashboard/carnadas", status_code=303)


@router.post("/carnadas/bulk-delete")
async def bulk_delete_carnadas(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    ids = [int(x) for x in form.getlist("selected_ids") if x.isdigit()]
    if ids:
        db.query(LanguageCarnada).filter(LanguageCarnada.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
    return RedirectResponse("/dashboard/carnadas", status_code=303)


@router.get("/carnadas/{carnada_id}/edit")
def edit_carnada_form(carnada_id: int, request: Request, db: Session = Depends(get_db)):
    c = db.query(LanguageCarnada).filter(LanguageCarnada.id == carnada_id).first()
    if not c:
        raise HTTPException(404, "No encontrado")
    return request.app.state.templates.TemplateResponse(request, "carnadas/edit.html", {
        "request": request, "item": c, "locales": META_LOCALES,
    })


@router.post("/carnadas/{carnada_id}/edit")
def edit_carnada(
    carnada_id: int,
    db: Session = Depends(get_db),
    locale_id: int = Form(...),
    body: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    url: str = Form(...),
    notes: str = Form(""),
):
    c = db.query(LanguageCarnada).filter(LanguageCarnada.id == carnada_id).first()
    if not c:
        raise HTTPException(404, "No encontrado")
    info = locale_by_id(locale_id)
    if not info:
        raise HTTPException(400, "Locale ID no reconocido")
    c.locale_id = locale_id
    c.locale_code = info["code"]
    c.language_name = info["name"]
    c.body = body
    c.title = title
    c.description = description
    c.url = url
    c.notes = notes
    db.commit()
    return RedirectResponse("/dashboard/carnadas", status_code=303)


# ─────────────────────────────────────────────────────────────────
# COPY BUNDLES
# ─────────────────────────────────────────────────────────────────

@router.get("/copies")
def list_copies(request: Request, db: Session = Depends(get_db)):
    items = db.query(CopyBundle).order_by(CopyBundle.created_at.desc()).all()
    return request.app.state.templates.TemplateResponse(request, "copies/list.html", {
        "request": request, "items": items,
    })


@router.get("/copies/new")
def new_copy(request: Request, db: Session = Depends(get_db)):
    carnadas = db.query(LanguageCarnada).order_by(LanguageCarnada.language_name).all()
    return request.app.state.templates.TemplateResponse(request, "copies/create.html", {
        "request": request, "locales": META_LOCALES, "carnadas": carnadas,
    })


@router.post("/copies")
async def create_copy(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        target_locale_id = int(form.get("target_locale_id", "6"))
    except ValueError:
        target_locale_id = 6
    info = locale_by_id(target_locale_id) or {"code": "en_XX"}

    # Respeta el orden de clic (carnada_order viene del JS); si no, cae al orden DOM
    order_raw = form.get("carnada_order", "")
    ordered_ids = [int(x) for x in order_raw.split(",") if x.strip().isdigit()] if order_raw else []
    selected_ids = {int(x) for x in form.getlist("carnada_ids") if x.isdigit()}
    carnada_ids = [i for i in ordered_ids if i in selected_ids]
    # añadir los que quedaron sin orden (defensa)
    for i in selected_ids:
        if i not in carnada_ids:
            carnada_ids.append(i)

    bundle = CopyBundle(
        name=form.get("name", "untitled"),
        real_body=form.get("real_body", ""),
        real_title=form.get("real_title", ""),
        real_desc=form.get("real_desc", ""),
        real_url=form.get("real_url", ""),
        target_locale_id=target_locale_id,
        target_locale_code=info["code"],
        carnada_ids=carnada_ids,
        # legacy compat
        real_label=info["code"],
        real_locales=[target_locale_id],
        default_copy={},
    )
    db.add(bundle)
    db.commit()
    return RedirectResponse("/dashboard/copies", status_code=303)


@router.post("/copies/{copy_id}/delete")
def delete_copy(copy_id: int, db: Session = Depends(get_db)):
    c = db.query(CopyBundle).filter(CopyBundle.id == copy_id).first()
    if c:
        db.delete(c)
        db.commit()
    return RedirectResponse("/dashboard/copies", status_code=303)


@router.get("/copies/{copy_id}/edit")
def edit_copy_form(copy_id: int, request: Request, db: Session = Depends(get_db)):
    c = db.query(CopyBundle).filter(CopyBundle.id == copy_id).first()
    if not c:
        raise HTTPException(404, "No encontrado")
    carnadas = db.query(LanguageCarnada).order_by(LanguageCarnada.language_name).all()
    selected_ids = c.carnada_ids or []
    return request.app.state.templates.TemplateResponse(request, "copies/edit.html", {
        "request": request, "item": c, "locales": META_LOCALES,
        "carnadas": carnadas, "selected_ids": selected_ids,
    })


@router.post("/copies/{copy_id}/edit")
async def edit_copy(copy_id: int, request: Request, db: Session = Depends(get_db)):
    c = db.query(CopyBundle).filter(CopyBundle.id == copy_id).first()
    if not c:
        raise HTTPException(404, "No encontrado")
    form = await request.form()
    try:
        target_locale_id = int(form.get("target_locale_id", "6"))
    except ValueError:
        target_locale_id = 6
    info = locale_by_id(target_locale_id) or {"code": "en_XX"}

    order_raw = form.get("carnada_order", "")
    ordered_ids = [int(x) for x in order_raw.split(",") if x.strip().isdigit()] if order_raw else []
    selected_ids = {int(x) for x in form.getlist("carnada_ids") if x.isdigit()}
    carnada_ids = [i for i in ordered_ids if i in selected_ids]
    for i in selected_ids:
        if i not in carnada_ids:
            carnada_ids.append(i)

    c.name = form.get("name", c.name)
    c.real_body = form.get("real_body", "")
    c.real_title = form.get("real_title", "")
    c.real_desc = form.get("real_desc", "")
    c.real_url = form.get("real_url", "")
    c.target_locale_id = target_locale_id
    c.target_locale_code = info["code"]
    c.carnada_ids = carnada_ids
    db.commit()
    return RedirectResponse("/dashboard/copies", status_code=303)


# ─────────────────────────────────────────────────────────────────
# WIZARD: Selector de tipo + Campaña de idiomas con N ads
# ─────────────────────────────────────────────────────────────────

@router.get("/campaigns/new-type")
def new_campaign_type(request: Request):
    return request.app.state.templates.TemplateResponse(request, "campaigns/new_type.html", {
        "request": request,
    })


@router.get("/campaigns/new-language")
def new_lang_wizard(request: Request, db: Session = Depends(get_db)):
    return _render_language_wizard(request, db)


@router.get("/campaigns/new-normal")
def new_normal_wizard(request: Request, db: Session = Depends(get_db)):
    return _render_normal_wizard(request, db)


@router.get("/campaigns/{camp_id}/duplicate")
def duplicate_campaign(camp_id: int, request: Request, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == camp_id).first()
    if not campaign:
        raise HTTPException(404, "Campaña no encontrada")

    config = dict(campaign.config or {})
    config.pop("result", None)
    config["name"] = f"{config.get('name') or campaign.name or 'Campaña'} (copia)"

    import re
    ad_indices = set()
    for key in config.keys():
        match = re.match(r"^ads\[(\d+)\]\[", str(key))
        if match:
            ad_indices.add(int(match.group(1)))
    if ad_indices:
        config["_clone_ads_count"] = max(ad_indices) + 1
    elif isinstance(config.get("ads"), list) and config["ads"]:
        config["_clone_ads_count"] = len(config["ads"])
    else:
        config["_clone_ads_count"] = 1

    campaign_type = (campaign.campaign_type or config.get("campaign_type") or "normal").lower()
    if campaign_type == "language":
        config["_locale_ids"] = config.get("adset_locale_ids") or config.get("adset_locale_id") or "6"
        return _render_language_wizard(request, db, form=config)

    config["_locale_ids"] = config.get("locale_ids") or config.get("locale_id") or "6"
    return _render_normal_wizard(request, db, form=config)


@router.post("/campaigns/new-normal")
async def post_normal_wizard(request: Request, db: Session = Depends(get_db)):
    try:
        form = await request.form()
        form_config = {k: v for k, v in form.items()}
        token = get_active_token(db)
        if not token:
            raise HTTPException(400, "No hay conexion Meta activa")

        act = form.get("ad_account_id", "").strip()
        if not act.startswith("act_"):
            act = f"act_{act}"

        import re
        ad_indices = set()
        pattern = re.compile(r"^ads\[(\d+)\]\[")
        for key in form.keys():
            m = pattern.match(key)
            if m:
                ad_indices.add(int(m.group(1)))
        if not ad_indices:
            raise HTTPException(400, "Necesitas al menos 1 ad")

        ads_data = []
        for idx in sorted(ad_indices):
            media_id_raw = form.get(f"ads[{idx}][media_asset_id]")
            if not media_id_raw:
                continue
            asset = db.query(MediaAsset).filter(MediaAsset.id == int(media_id_raw)).first()
            if not asset:
                raise HTTPException(400, f"Ad #{idx+1}: creativo no encontrado")
            if not asset.uploaded_to_meta or not asset.meta_id:
                raise HTTPException(400, f"El creativo '{asset.name}' no está en Meta. Ve a /media y dale 'Subir a Meta'.")

            ads_data.append({
                "is_video": asset.type == "video",
                "meta_id": asset.meta_id,
                "body": form.get(f"ads[{idx}][body]", ""),
                "title": form.get(f"ads[{idx}][title]", ""),
                "description": form.get(f"ads[{idx}][description]", ""),
                "link": form.get(f"ads[{idx}][link]", ""),
                "cta_type": form.get(f"ads[{idx}][cta_type]", "LEARN_MORE"),
                "ad_name": form.get(f"ads[{idx}][ad_name]", "").strip(),
            })

        if not ads_data:
            raise HTTPException(400, "No completaste ningún ad")

        countries = [c.strip().upper() for c in form.get("countries", "US").split(",") if c.strip()] or ["US"]
        bid_amount_raw = (form.get("bid_amount") or "").strip()
        bid_amount_cents = int(float(bid_amount_raw) * 100) if bid_amount_raw else 0
        roas_floor_raw = (form.get("roas_floor") or "").strip()
        roas_floor = float(roas_floor_raw) if roas_floor_raw else 0.0

        raw_ids_n = form.getlist("locale_id") if hasattr(form, "getlist") else []
        if not raw_ids_n:
            raw_ids_n = [form.get("locale_id", "6")]
        try:
            locale_ids_n = [int(x) for x in raw_ids_n if str(x).strip().isdigit()]
        except ValueError:
            locale_ids_n = [6]
        primary_locale_n = locale_ids_n[0] if locale_ids_n else 6

        from ..services.normal_campaign import create_normal_multi_ad
        result = create_normal_multi_ad(
            act_id=act, token=token,
            page_id=form["page_id"], pixel_id=form["pixel_id"],
            name=form["name"],
            countries=countries,
            age_min=int(form.get("age_min", "18")),
            age_max=int(form.get("age_max", "65")),
            locale_id=primary_locale_n,
            locale_ids=locale_ids_n,
            daily_budget_cents=int(float(form.get("daily_budget_usd", "5")) * 100),
            is_cbo=(form.get("cbo_or_abo", "ABO") == "CBO"),
            ads=ads_data,
            objective=form.get("objective", "OUTCOME_SALES"),
            optimization_goal=form.get("optimization_goal", "OFFSITE_CONVERSIONS"),
            custom_event_type=form.get("custom_event_type", "PURCHASE"),
            bid_strategy=form.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP"),
            bid_amount_cents=bid_amount_cents,
            roas_floor=roas_floor,
            instagram_id=form.get("instagram_id", "").strip(),
            url_tags=form.get("url_tags", ""),
            adset_name=form.get("adset_name", "").strip(),
            start_time=form.get("start_time", "").strip(),
            end_time=form.get("end_time", "").strip(),
        )
        if result.get("errors"):
            message, details = _format_campaign_errors(result)
            return _render_normal_wizard(request, db, error=message, error_details=details, status_code=400)

        saved = _save_created_campaign(
            db,
            name=form["name"],
            ad_account_id=act,
            campaign_type="normal",
            result=result,
            config={**form_config, "locale_ids": locale_ids_n, "ads": ads_data, "result": result},
        )
        return RedirectResponse(f"/dashboard/campaigns?created={saved.id}", status_code=303)
    except HTTPException as exc:
        return _render_normal_wizard(request, db, error=str(exc.detail), error_details=[str(exc.detail)], status_code=400)
    except Exception as exc:
        return _render_normal_wizard(request, db, error=f"No se pudo crear la campaña normal: {exc}", error_details=[str(exc)], status_code=400)


@router.post("/campaigns/new-language")
async def post_lang_wizard(request: Request, db: Session = Depends(get_db)):
    try:
        form = await request.form()
        form_config = {k: v for k, v in form.items()}
        token = get_active_token(db)
        if not token:
            raise HTTPException(400, "No hay conexion Meta activa")

        act = form.get("ad_account_id", "").strip()
        if not act.startswith("act_"):
            act = f"act_{act}"

        import re
        ad_indices = set()
        pattern = re.compile(r"^ads\[(\d+)\]\[")
        for key in form.keys():
            m = pattern.match(key)
            if m:
                ad_indices.add(int(m.group(1)))

        if not ad_indices:
            raise HTTPException(400, "Necesitas al menos 1 ad")

        ads_data = []
        for idx in sorted(ad_indices):
            media_id_raw = form.get(f"ads[{idx}][media_asset_id]")
            default_id_raw = form.get(f"ads[{idx}][default_media_id]")
            copy_id_raw = form.get(f"ads[{idx}][copy_bundle_id]")
            if not (media_id_raw and default_id_raw and copy_id_raw):
                continue

            real_asset = db.query(MediaAsset).filter(MediaAsset.id == int(media_id_raw)).first()
            default_asset = db.query(MediaAsset).filter(MediaAsset.id == int(default_id_raw)).first()
            bundle = db.query(CopyBundle).filter(CopyBundle.id == int(copy_id_raw)).first()
            if not (real_asset and default_asset and bundle):
                raise HTTPException(400, f"Ad #{idx+1}: asset o bundle no encontrado")

            for a in (real_asset, default_asset):
                if not a.uploaded_to_meta or not a.meta_id:
                    raise HTTPException(400, f"El creativo '{a.name}' aún no se subió a Meta. Ve a /media y dale 'Subir a Meta'.")

            carnadas_objs = db.query(LanguageCarnada).filter(
                LanguageCarnada.id.in_(bundle.carnada_ids or [])
            ).all()
            if not carnadas_objs:
                raise HTTPException(400, f"El paquete '{bundle.name}' no tiene carnadas")
            carnadas_by_id = {c.id: c for c in carnadas_objs}
            carnadas_ordered = [carnadas_by_id[i] for i in (bundle.carnada_ids or []) if i in carnadas_by_id]

            carnadas = [{
                "locale_id": c.locale_id, "locale_code": c.locale_code,
                "body": c.body, "title": c.title, "desc": c.description, "url": c.url,
            } for c in carnadas_ordered]

            ads_data.append({
                "target_locale_id": bundle.target_locale_id or 6,
                "target_locale_code": bundle.target_locale_code or "en_XX",
                "real_media_id": real_asset.meta_id,
                "default_media_id": default_asset.meta_id,
                "is_video": real_asset.type == "video",
                "real_body": bundle.real_body,
                "real_title": bundle.real_title,
                "real_desc": bundle.real_desc or "",
                "real_url": bundle.real_url,
                "url_tags": form.get("url_tags", ""),
                "carnadas": carnadas,
                "cta_type": form.get(f"ads[{idx}][cta_type]", "LEARN_MORE"),
                "ad_name": form.get(f"ads[{idx}][ad_name]", "").strip(),
            })

        if not ads_data:
            raise HTTPException(400, "No completaste ningún ad (falta creativo/copy en todos los slots)")

        countries = [c.strip().upper() for c in form.get("countries", "US").split(",") if c.strip()]
        if not countries:
            countries = ["US"]

        bid_amount_raw = (form.get("bid_amount") or "").strip()
        bid_amount_cents = int(float(bid_amount_raw) * 100) if bid_amount_raw else 0
        roas_floor_raw = (form.get("roas_floor") or "").strip()
        roas_floor = float(roas_floor_raw) if roas_floor_raw else 0.0

        raw_ids = form.getlist("adset_locale_id") if hasattr(form, "getlist") else []
        if not raw_ids:
            raw_ids = [form.get("adset_locale_id", "6")]
        try:
            adset_locale_ids = [int(x) for x in raw_ids if str(x).strip().isdigit()]
        except ValueError:
            adset_locale_ids = [6]
        primary_locale_id = adset_locale_ids[0] if adset_locale_ids else 6

        from ..services.language_trick import create_language_trick_multi_ad
        result = create_language_trick_multi_ad(
            act_id=act,
            token=token,
            page_id=form["page_id"],
            pixel_id=form["pixel_id"],
            name=form["name"],
            countries=countries,
            age_min=int(form.get("age_min", "40")),
            age_max=int(form.get("age_max", "65")),
            adset_locale_id=primary_locale_id,
            adset_locale_ids=adset_locale_ids,
            daily_budget_cents=int(float(form.get("daily_budget_usd", "1.50")) * 100),
            is_cbo=(form.get("cbo_or_abo", "ABO") == "CBO"),
            ads=ads_data,
            objective=form.get("objective", "OUTCOME_SALES"),
            optimization_goal=form.get("optimization_goal", "OFFSITE_CONVERSIONS"),
            custom_event_type=form.get("custom_event_type", "PURCHASE"),
            bid_strategy=form.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP"),
            bid_amount_cents=bid_amount_cents,
            roas_floor=roas_floor,
            instagram_id=form.get("instagram_id", "").strip(),
            adset_name=form.get("adset_name", "").strip(),
            start_time=form.get("start_time", "").strip(),
            end_time=form.get("end_time", "").strip(),
        )

        if result.get("errors"):
            message, details = _format_campaign_errors(result)
            return _render_language_wizard(request, db, error=message, error_details=details, status_code=400)

        saved = _save_created_campaign(
            db,
            name=form["name"],
            ad_account_id=act,
            campaign_type="language",
            result=result,
            config={**form_config, "adset_locale_ids": adset_locale_ids, "ads": ads_data, "result": result},
        )
        return RedirectResponse(f"/dashboard/campaigns?created={saved.id}", status_code=303)
    except HTTPException as exc:
        return _render_language_wizard(request, db, error=str(exc.detail), error_details=[str(exc.detail)], status_code=400)
    except Exception as exc:
        return _render_language_wizard(request, db, error=f"No se pudo crear la campaña con truco de idiomas: {exc}", error_details=[str(exc)], status_code=400)


# ─────────────────────────────────────────────────────────────────
# LANGUAGE TRICK CAMPAIGN (single-ad, legacy)
# ─────────────────────────────────────────────────────────────────

@router.post("/campaigns/language-trick")
async def create_lang_campaign(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    token = get_active_token(db)
    if not token:
        raise HTTPException(400, "No hay conexion Meta activa")

    real_asset = db.query(MediaAsset).filter(MediaAsset.id == int(form["media_asset_id"])).first()
    default_asset = db.query(MediaAsset).filter(MediaAsset.id == int(form["default_media_id"])).first()
    copy_bundle = db.query(CopyBundle).filter(CopyBundle.id == int(form["copy_bundle_id"])).first()

    if not real_asset or not default_asset or not copy_bundle:
        raise HTTPException(400, "Faltan assets o copy bundle")

    act = form["ad_account_id"]
    if not act.startswith("act_"):
        act = f"act_{act}"

    # Auto-subir a Meta si todavía no se subieron
    for asset in (real_asset, default_asset):
        if not asset.uploaded_to_meta or not asset.meta_id:
            raise HTTPException(400, f"El creativo '{asset.name}' aún no se subió a Meta. Ve a /media y dale 'Subir a Meta'.")

    # Construir lista de carnadas desde el bundle
    carnadas_objs = db.query(LanguageCarnada).filter(
        LanguageCarnada.id.in_(copy_bundle.carnada_ids or [])
    ).all()
    carnadas = [{
        "locale_id": c.locale_id, "locale_code": c.locale_code,
        "body": c.body, "title": c.title, "desc": c.description, "url": c.url,
    } for c in carnadas_objs]

    if not carnadas:
        raise HTTPException(400, "El paquete de copy no tiene carnadas seleccionadas.")

    is_video = real_asset.type == "video"

    result = create_language_trick_campaign(
        act_id=act,
        token=token,
        page_id=form["page_id"],
        pixel_id=form["pixel_id"],
        name=form["name"],
        country=form.get("country", "US"),
        age_min=int(form.get("age_min", "40")),
        age_max=int(form.get("age_max", "65")),
        target_locale_id=copy_bundle.target_locale_id,
        target_locale_code=copy_bundle.target_locale_code,
        real_media_id=real_asset.meta_id,
        default_media_id=default_asset.meta_id,
        is_video=is_video,
        real_body=copy_bundle.real_body,
        real_title=copy_bundle.real_title,
        real_desc=copy_bundle.real_desc or "",
        real_url=copy_bundle.real_url,
        url_tags=form.get("url_tags", ""),
        daily_budget_cents=int(float(form.get("daily_budget_usd", "1.50")) * 100),
        carnadas=carnadas,
        is_cbo=(form.get("cbo_or_abo", "ABO") == "CBO"),
    )

    if result.get("errors"):
        message, details = _format_campaign_errors(result)
        return _render_language_wizard(request, db, error=message, error_details=details, status_code=400)
    saved = _save_created_campaign(
        db,
        name=form["name"],
        ad_account_id=act,
        campaign_type="language",
        result=result,
        config={k: v for k, v in form.items()} | {"result": result},
    )
    return RedirectResponse(f"/dashboard/campaigns?created={saved.id}", status_code=303)
