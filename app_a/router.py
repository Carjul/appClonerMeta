"""
app_a/router.py
───────────────
Router agregador de App A (Jinja2).

Incluye todos los sub-routers con prefix=/dashboard para que
sus rutas queden bajo /dashboard/* en el servidor unificado.

La ruta home (/dashboard) también vive aquí, movida desde
el main.py original de App A.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from .database import get_db
from .meta_connections import get_active_connection, get_active_token
from .models import Catalog, Campaign, CampaignTemplate, Product, ProductSet
from .config import PUBLIC_BASE_URL
from .routers import (
    campaigns,
    catalogs,
    feed,
    language_routes,
    planning,
    products,
    sets,
    setup,
    templates as tpl_router,
    trick,
)

# ── Router principal con prefix /dashboard ────────────────────────
router = APIRouter(prefix="/dashboard", default_response_class=HTMLResponse)

# Sub-routers — heredan el prefix /dashboard automáticamente
router.include_router(setup.router)
router.include_router(catalogs.router)
router.include_router(products.router)
router.include_router(sets.router)
router.include_router(campaigns.router)
router.include_router(tpl_router.router)
router.include_router(trick.router)
router.include_router(feed.router)
router.include_router(language_routes.router)
router.include_router(planning.router)


# ── Home: GET /dashboard ──────────────────────────────────────────
@router.get("", include_in_schema=False)
@router.get("/", include_in_schema=False)
def home(request: Request, db=Depends(get_db)):
    """Página de inicio del dashboard (Jinja2)."""
    active_connection = get_active_connection(db)
    stats = {
        "catalogs":  db.query(Catalog).count(),
        "products":  db.query(Product).count(),
        "sets":      db.query(ProductSet).count(),
        "campaigns": db.query(Campaign).count(),
        "templates": db.query(CampaignTemplate).count(),
    }
    pending_trick = db.query(Campaign).filter(
        Campaign.trick_enabled == True,
        Campaign.trick_executed == False,
    ).count()

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "request":          request,
            "stats":            stats,
            "pending_trick":    pending_trick,
            "token_set":        bool(get_active_token(db)),
            "active_connection": active_connection,
            "public_base":      PUBLIC_BASE_URL,
        },
    )
