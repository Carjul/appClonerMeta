# Meta Automation Web

Aplicación web para automatización de Meta Ads con:

- **Backend FastAPI unificado** en `backend/`
- **Frontend React/Vite** en `frontend/`
- **Scripts individuales** en la raíz del proyecto

## Estructura

```text
app/
├─ backend/
│  ├─ main.py                 # entrada principal: backend.main:app
│  ├─ core/                   # configuración unificada
│  ├─ api/                    # API JSON, jobs, métricas y build React
│  ├─ dashboard/              # dashboard Jinja en /dashboard
│  ├─ app/                    # wrapper legacy
│  ├─ legacy/                 # código anterior preservado
│  ├─ ARCHITECTURE.md         # documentación técnica de rutas/conexiones
│  └─ requirements.txt
├─ frontend/
├─ meta_bm_explorer.py
├─ meta_bulk_clone_fixed.py
├─ Meta_clone_fixed.py
├─ meta_ads_delete.py
├─ meta_campaign_status.py
├─ reduce_budgets.py
├─ fb_daily_report.py
├─ fb_rules_engine.py
├─ Dockerfile
└─ main.py                    # wrapper legacy hacia backend.main:app
```

Más detalle técnico: [backend/ARCHITECTURE.md](backend/ARCHITECTURE.md)

## Backend

Instalar dependencias:

```bash
pip install -r backend/requirements.txt
```

Ejecutar servidor:

```bash
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Compatibilidad conservada:

```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Variables de entorno

El backend lee el `.env` ubicado en la raíz del proyecto.

Variables principales:

```env
MONGO_URI=mongodb://localhost:27017
DB_NAME=meta_automation
PYTHON_BIN=python
```

También funciona `MONGODB_URI` como alternativa a `MONGO_URI`.

## Rutas principales

- `GET/POST /login` — login simple contra MongoDB `Users`
- `GET /logout` — cerrar sesión
- `GET /api/auth/me` — usuario/rol actual
- `GET /` — React SPA
- `GET /api/health`
- `GET/POST/PUT/DELETE /api/configs`
- `POST /api/explorer/run`
- `GET /api/explorer/{job_id}/result`
- `POST /api/clone/bulk`
- `POST /api/clone/single`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/logs`
- `POST /api/jobs/{job_id}/cancel`
- `GET /dashboard` — dashboard Jinja
- `GET /metricas` — dashboard de métricas
- `GET /metricas/api/token-status` — verificación segura de tokens Mongo

## Autenticación

Usuarios en MongoDB:

```text
database: meta_automation
collection: Users
fields: Name, Password, Rol, Configs_Id
```

- `Admin` entra a `/` y puede usar todo.
- `Cliente` entra a `/metricas` y puede usar `/metricas/api/*`.

## Métricas

`/metricas` no usa tokens desde `.env`.

Los tokens se leen desde MongoDB:

```text
database: meta_automation
collection: configs
field: access_token
```

Se usan los primeros 2 configs como:

- `BM1`
- `BM2`

## Frontend

Instalar dependencias:

```bash
cd frontend
npm install
```

Desarrollo:

```bash
npm run dev
```

Build:

```bash
npm run build
```

El build sale en:

```text
backend/api/static/
```

## Docker

Construir imagen desde la raíz:

```bash
docker build -t meta-backend .
```

Ejecutar:

```bash
docker run --rm -p 8000:8000 --env-file .env meta-backend
```

El contenedor usa:

```bash
python -m uvicorn backend.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}
```

## Flujo básico

1. Crear configuraciones en **Configuración**: nombre, BM ID y token.
2. En **Campañas**, seleccionar configuración y cargar cuentas/campañas.
3. Lanzar clonación bulk o single.
4. Revisar jobs, logs y cancelar si hace falta.
5. Revisar métricas en `/metricas`.
