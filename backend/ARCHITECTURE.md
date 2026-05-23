# Backend Architecture

Este proyecto quedó organizado para que **todo el backend viva dentro de `backend/`**, mientras `frontend/` y los scripts individuales permanecen al nivel raíz.

## Estructura actual

```text
app/
├─ backend/
│  ├─ main.py                 # FastAPI principal: backend.main:app
│  ├─ core/                   # configuración unificada (.env raíz)
│  ├─ api/                    # API JSON, jobs, Mongo, métricas y React build
│  │  ├─ routes/              # /api/* y /feed/*
│  │  ├─ services/            # runners, scheduler, Meta API helpers
│  │  ├─ static/              # build del frontend React servido en /
│  │  └─ metrics_dashboard_pro.py # /metricas y /metricas/api/*
│  ├─ dashboard/              # dashboard Jinja/FastAPI servido en /dashboard
│  ├─ app/                    # wrapper legacy: backend/app/main.py -> backend.main:app
│  ├─ legacy/                 # código anterior preservado, no activo
│  └─ requirements.txt        # dependencias Python del backend
├─ frontend/                  # React/Vite al mismo nivel que backend
├─ *.py                       # scripts individuales usados por jobs
├─ main.py                    # wrapper legacy: from backend.main import app
├─ Dockerfile
└─ README.md
```

## Punto de entrada canónico

Usar siempre:

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Compatibilidad conservada:

- `uvicorn main:app` sigue funcionando desde la raíz.
- `cd backend && uvicorn app.main:app` sigue funcionando mediante wrapper legacy.

## Rutas públicas conservadas

Estas rutas se mantienen igual:

- `/` → React SPA
- `/assets/*` → assets React
- `/api/health`
- `/api/configs`
- `/api/explorer/*`
- `/api/clone/*`
- `/api/delete/*`
- `/api/campaigns/status`
- `/api/budgets/reduce`
- `/api/fb-catalog/*`
- `/feed/*`
- `/api/jobs/*`
- `/api/daily-report/*`
- `/api/rules/*`
- `/dashboard/*`
- `/static/*`
- `/metricas`
- `/metricas/*`
- `/metricas/api/*`

## Autenticación simple

La autenticación se implementa en `backend/auth.py` y usa sesiones firmadas con `SessionMiddleware`.

Usuarios:

```text
MongoDB database: meta_automation
collection: Users
fields: Name, Password, Rol, Configs_Id
```

Reglas actuales:

- Sin sesión: cualquier ruta protegida redirige a `/login`.
- `Rol = Admin`: puede usar todas las rutas y `/login` lo redirige a `/`.
- `Rol = Cliente`: entra a `/metricas` y puede usar todas las rutas bajo `/metricas` incluyendo `/metricas/api/*`; también puede usar `/api/auth/me` y `/logout`.
- Logout: `/logout` limpia sesión y vuelve a `/login`.

> Nota: las contraseñas están en texto plano porque así existen actualmente en Mongo. Queda pendiente migrarlas a hash cuando se quiera reforzar seguridad.

## Conexiones y datos

### MongoDB principal

La configuración se carga desde `backend/core/config.py`, que lee el `.env` de la raíz del proyecto.

Variables principales:

- `MONGO_URI` o `MONGODB_URI`
- `DB_NAME` default: `meta_automation`

Colecciones usadas por `backend/api/db.py`:

- `configs`
- `jobs`
- `job_logs`
- `daily_reports`
- `rules`
- `rules_logs`
- `fb_catalogs`
- `fb_products`
- `fb_product_sets`
- `fb_campaign_templates`
- `fb_campaigns`
- `fb_media_assets`
- `fb_language_carnadas`
- `fb_copy_bundles`
- `fb_planned_campaigns`

### Métricas `/metricas`

`/metricas` **no usa tokens BM desde `.env`**.

Lee los dos tokens desde:

```text
MongoDB database: meta_automation
collection: configs
field: access_token
```

Endpoint seguro de verificación:

```text
GET /metricas/api/token-status
```

Este endpoint muestra origen, base de datos, colección y cantidad de tokens, **sin exponer tokens**.

### Dashboard `/dashboard`

El dashboard Jinja vive en `backend/dashboard/` y conserva sus rutas bajo `/dashboard/*`.

Usa su configuración desde `backend/dashboard/config.py`, leyendo también el `.env` raíz.

### Scripts individuales

Los scripts siguen en la raíz del proyecto. Los jobs de `backend/api/services/meta_runner.py` calculan `ROOT_DIR` como la raíz del proyecto para ejecutar comandos como:

- `fb_daily_report.py`
- `meta_bulk_clone_fixed.py`
- `Meta_clone_fixed.py`
- `meta_ads_delete.py`
- `meta_campaign_status.py`
- `reduce_budgets.py`

Los artifacts siguen guardándose en:

```text
logs/artifacts/
```

## Frontend

`frontend/vite.config.js` genera el build en:

```text
backend/api/static/
```

FastAPI sirve ese build como SPA raíz (`/`).

## Docker

El Dockerfile usa:

```bash
python -m uvicorn backend.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}
```

Y copia el build de React hacia:

```text
backend/api/static
```

## Código legacy preservado

La antigua implementación duplicada `backend/app/` se preservó en:

```text
backend/legacy/app_old/
```

Scripts antiguos que estaban duplicados dentro de `backend/` se preservaron en:

```text
backend/legacy/scripts_old/
```

No son rutas activas. Están conservados para referencia y recuperación si hiciera falta.

## Checklist rápido de salud

Después de cambios estructurales, verificar:

```bash
python -m py_compile backend/main.py backend/api/metrics_dashboard_pro.py
```

Endpoints recomendados:

```text
GET /
GET /api/health
GET /api/configs
GET /dashboard
GET /metricas
GET /metricas/api/token-status
GET /metricas/api/bootstrap
```
