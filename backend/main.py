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

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.wsgi import WSGIMiddleware

from backend.core.config import settings
from backend.auth import SESSION_KEY, authenticate_user, current_user, is_admin, is_client, landing_for, login_page

# ── App B: routers API ────────────────────────────────────────────
from backend.api.routes.configs       import router as configs_router
from backend.api.routes.daily_report  import router as daily_report_router
from backend.api.routes.fb_catalog    import public_router as fb_catalog_public_router
from backend.api.routes.fb_catalog    import router as fb_catalog_router
from backend.api.routes.jobs          import router as jobs_router
from backend.api.routes.meta          import router as meta_router
from backend.api.routes.rules_engine  import router as rules_engine_router

# ── App B: servicios en segundo plano ────────────────────────────
from backend.api.services.fb_catalog_planning_runner import (
    fb_catalog_planning_runner_state,
    start_fb_catalog_planning_runner,
    stop_fb_catalog_planning_runner,
)
from backend.api.services.fb_catalog_trick_runner import (
    fb_catalog_trick_runner_state,
    start_fb_catalog_trick_runner,
    stop_fb_catalog_trick_runner,
)
from backend.api.services.scheduler import scheduler_state, start_scheduler, stop_scheduler

# ── App A: router Jinja2 ─────────────────────────────────────────
from backend.dashboard.router import router as jinja_router

# ── Dashboard de métricas adjunto (Flask/WSGI) ───────────────────
from backend.api.metrics_dashboard_pro import HTML as metrics_dashboard_html
from backend.api.metrics_dashboard_pro import app as metrics_dashboard_app

# ── App A: DB, migraciones y trick-runner propio ─────────────────
from backend.dashboard.database         import create_db_session, migrate_db
from backend.dashboard.meta_connections import get_active_token, upsert_env_connection
from backend.dashboard.trick_runner     import start_scheduler as start_trick_scheduler
from backend.dashboard.trick_runner     import stop_scheduler  as stop_trick_scheduler

# ── Directorios ───────────────────────────────────────────────────
BASE_DIR            = Path(__file__).resolve().parent
APP_A_STATIC_DIR    = BASE_DIR / "dashboard" / "static"
APP_A_TEMPLATES_DIR = BASE_DIR / "dashboard" / "templates"
APP_B_REACT_DIR     = BASE_DIR / "api" / "static"


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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


PUBLIC_PATHS = {
    "/login",
    "/favicon.svg",
}


def _is_public_asset(path: str) -> bool:
    return path.startswith("/assets/") or path.startswith("/static/")


def _is_metrics_path(path: str) -> bool:
    return path == "/metricas" or path.startswith("/metricas/")


def _is_auth_api(path: str) -> bool:
    return path == "/api/auth/me"


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    if path in PUBLIC_PATHS or _is_public_asset(path):
        user = current_user(request)
        if path == "/login" and user:
            return RedirectResponse(url=landing_for(user), status_code=303)
        return await call_next(request)

    user = current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if is_admin(user):
        return await call_next(request)

    if is_client(user):
        if _is_metrics_path(path) or _is_auth_api(path) or path == "/logout":
            return await call_next(request)
        return RedirectResponse(url="/metricas", status_code=303)

    request.session.pop(SESSION_KEY, None)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/login", include_in_schema=False)
def login_get(request: Request):
    user = current_user(request)
    if user:
        return RedirectResponse(url=landing_for(user), status_code=303)
    return login_page()


@app.post("/login", include_in_schema=False)
async def login_post(request: Request):
    form = await request.form()
    username = str(form.get("username") or "")
    password = str(form.get("password") or "")
    user = authenticate_user(username, password)
    if not user:
        return login_page("Usuario o contraseña inválidos")
    request.session[SESSION_KEY] = user
    return RedirectResponse(url=landing_for(user), status_code=303)


@app.get("/logout", include_in_schema=False)
def logout_get(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.post("/logout", include_in_schema=False)
def logout_post(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/api/auth/me", tags=["auth"])
def auth_me(request: Request):
    user = current_user(request)
    if not user:
        return JSONResponse({"authenticated": False}, status_code=401)
    return {"authenticated": True, "user": user}


# SessionMiddleware requerido por App A y por auth.
# Se agrega después del middleware de auth para que sea más externo
# y request.session esté disponible dentro de auth_middleware.
app.add_middleware(SessionMiddleware, secret_key=settings.APP_A_SECRET_KEY)


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
# 4. DASHBOARD MÉTRICAS — /metricas/*
#    Montado antes del catch-all de React para que no sea absorbido.
# ─────────────────────────────────────────────────────────────────
@app.get("/metricas", include_in_schema=False)
def serve_metricas_root():
    return HTMLResponse(metrics_dashboard_html)

app.mount("/metricas", WSGIMiddleware(metrics_dashboard_app), name="metricas")


# ─────────────────────────────────────────────────────────────────
# 5. ARCHIVOS ESTÁTICOS — montados después de los routers
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
