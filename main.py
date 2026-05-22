"""
╔══════════════════════════════════════════════════════════════════╗
║          PUNTO DE ENTRADA UNIFICADO – FastAPI                    ║
╠══════════════════════════════════════════════════════════════════╣
║  /            →  React SPA  (App B compilada)                   ║
║  /dashboard   →  Jinja2 Dashboard  (App A)                      ║
║  /api/*       →  REST/JSON API  (App B)                         ║
║  /static/*    →  CSS/JS de Jinja2                               ║
║  /assets/*    →  JS/CSS del build de React                      ║
╚══════════════════════════════════════════════════════════════════╝

Orden de evaluación (FastAPI evalúa en orden de registro):
  1. /api/*           → JSON routers App B   (mayor prioridad)
  2. /feed/*          → CSV público App B
  3. /dashboard/*     → Jinja2 router App A
  4. /static/*        → StaticFiles Jinja2
  5. /assets/*        → StaticFiles React build
  6. /favicon.svg     → favicon de la SPA
  7. /                → React index.html
  8. /{spa_path:path} → catch-all SPA React   (menor prioridad)

  El catch-all (8) solo se alcanza cuando ninguna ruta anterior
  coincide, por lo que /api/*, /dashboard/* y /static/* están
  SIEMPRE protegidos.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from core.config import settings

# ── App B: routers API ────────────────────────────────────────────
from app_b.routes.configs       import router as configs_router
from app_b.routes.daily_report  import router as daily_report_router
from app_b.routes.fb_catalog    import public_router as fb_catalog_public_router
from app_b.routes.fb_catalog    import router as fb_catalog_router
from app_b.routes.jobs          import router as jobs_router
from app_b.routes.meta          import router as meta_router
from app_b.routes.rules_engine  import router as rules_engine_router

# ── App B: servicios en segundo plano ────────────────────────────
from app_b.services.fb_catalog_planning_runner import (
    fb_catalog_planning_runner_state,
    start_fb_catalog_planning_runner,
    stop_fb_catalog_planning_runner,
)
from app_b.services.fb_catalog_trick_runner import (
    fb_catalog_trick_runner_state,
    start_fb_catalog_trick_runner,
    stop_fb_catalog_trick_runner,
)
from app_b.services.scheduler import scheduler_state, start_scheduler, stop_scheduler

# ── App A: router Jinja2 ─────────────────────────────────────────
from app_a.router import router as jinja_router

# ── App A: DB, migraciones y trick-runner propio ─────────────────
from app_a.database         import create_db_session, migrate_db
from app_a.meta_connections import get_active_token, upsert_env_connection
from app_a.trick_runner     import start_scheduler as start_trick_scheduler
from app_a.trick_runner     import stop_scheduler  as stop_trick_scheduler

# ── Directorios ───────────────────────────────────────────────────
BASE_DIR            = Path(__file__).resolve().parent
APP_A_STATIC_DIR    = BASE_DIR / "app_a" / "static"
APP_A_TEMPLATES_DIR = BASE_DIR / "app_a" / "templates"
APP_B_REACT_DIR     = BASE_DIR / "app_b" / "static"


# ─────────────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # App A ──────────────────────────────────────────────────────
    migrate_db()
    db = create_db_session()
    try:
        upsert_env_connection(db)
        if get_active_token(db):
            start_trick_scheduler()
    finally:
        db.close()

    # App B ──────────────────────────────────────────────────────
    start_scheduler()
    start_fb_catalog_trick_runner()
    start_fb_catalog_planning_runner()

    yield

    # Shutdown ───────────────────────────────────────────────────
    stop_trick_scheduler()
    stop_scheduler()
    stop_fb_catalog_trick_runner()
    stop_fb_catalog_planning_runner()


# ─────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Meta Automation Platform",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Templates de Jinja2 (accedidos por routers via request.app.state.templates)
app.state.templates = Jinja2Templates(directory=str(APP_A_TEMPLATES_DIR))

# SessionMiddleware requerido por App A
app.add_middleware(SessionMiddleware, secret_key=settings.APP_A_SECRET_KEY)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────
# 1. HEALTH
# ─────────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["system"])
def health():
    return {
        "ok": True,
        "scheduler": {
            "enabled": settings.SCHEDULER_ENABLED,
            "timezone": settings.SCHEDULER_TZ,
            "state": scheduler_state(),
        },
        "fbCatalogTrickRunner":    fb_catalog_trick_runner_state(),
        "fbCatalogPlanningRunner": fb_catalog_planning_runner_state(),
    }


# ─────────────────────────────────────────────────────────────────
# 2. ROUTERS APP B  —  /api/* y /feed/*
# ─────────────────────────────────────────────────────────────────
app.include_router(configs_router)            # /api/configs
app.include_router(daily_report_router)       # /api/daily-report
app.include_router(fb_catalog_router)         # /api/fb-catalog
app.include_router(fb_catalog_public_router)  # /feed/{slug}.csv
app.include_router(jobs_router)               # /api/jobs
app.include_router(meta_router)               # /api/explorer /api/clone …
app.include_router(rules_engine_router)       # /api/rules-engine


# ─────────────────────────────────────────────────────────────────
# 3. ROUTER APP A  —  /dashboard/*   (Jinja2)
#    Registrado ANTES del catch-all de React para que /dashboard/*
#    nunca sea absorbido por la SPA.
# ─────────────────────────────────────────────────────────────────
app.include_router(jinja_router)


# ─────────────────────────────────────────────────────────────────
# 4. ARCHIVOS ESTÁTICOS — montados después de los routers
# ─────────────────────────────────────────────────────────────────
if APP_A_STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=APP_A_STATIC_DIR), name="static")

if (APP_B_REACT_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=APP_B_REACT_DIR / "assets"), name="react_assets")


# ─────────────────────────────────────────────────────────────────
# 5. REACT SPA  —  sirve en /  con catch-all
#
#    Por qué no hay colisión con /dashboard ni /api:
#      FastAPI evalúa en orden de registro. Como jinja_router y los
#      API routers se registraron ANTES, sus rutas tienen prioridad.
#      El catch-all solo se ejecuta cuando NINGUNA ruta anterior
#      coincide.
# ─────────────────────────────────────────────────────────────────
_react_index = APP_B_REACT_DIR / "index.html"

@app.get("/favicon.svg", include_in_schema=False)
def serve_favicon():
    return FileResponse(APP_B_REACT_DIR / "favicon.svg")

@app.get("/", include_in_schema=False)
def serve_react_root():
    """Sirve la React SPA en la raíz."""
    return FileResponse(_react_index)

@app.get("/{spa_path:path}", include_in_schema=False)
def serve_react_spa(spa_path: str):
    """
    Catch-all: cualquier ruta que no coincida con /api/*, /dashboard/*
    ni archivos estáticos llega aquí y recibe el index.html de React,
    dejando que React Router maneje la navegación en el cliente.
    """
    # Bloquea explícitamente acceso a /api/ que llegue aquí por error
    if spa_path.startswith("api/"):
        raise HTTPException(status_code=404)

    # Sirve archivos físicos del build si existen (ej: robots.txt)
    file_path = APP_B_REACT_DIR / spa_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    # Para todo lo demás: React Router toma el control en el cliente
    return FileResponse(_react_index)
