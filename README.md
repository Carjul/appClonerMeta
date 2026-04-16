# Meta Automation Web

Aplicacion web para ejecutar tus scripts de Meta Ads desde API, con estado, logs y cancelacion de procesos.

## Estructura

- `backend/`: FastAPI + MongoDB
- `frontend/`: React + Vite
- Scripts originales usados por la API:
  - `meta_bm_explorer.py`
  - `meta_bulk_clone_fixed.py`
  - `Meta_clone_fixed.py`

## Backend

1. Instalar dependencias:

```bash
cd backend
pip install -r requirements.txt
```

2. Configurar entorno:

```bash
cp .env.example .env
```

La URI de Mongo se coloca en `backend/.env` en la variable `MONGO_URI`.
Ejemplo:

```env
MONGO_URI=mongodb://localhost:27017
DB_NAME=meta_automation
```

3. Ejecutar API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Frontend embebido en backend

Para servir el frontend desde FastAPI:

```bash
cd frontend
npm run build
cd ..
mkdir -p backend/app/static
cp -r frontend/dist/. backend/app/static/
```

Despues de eso, el backend responde tambien la UI en `/`.

## Docker (backend)

Construir imagen (desde la raiz del proyecto):

```bash
docker build -f backend/Dockerfile -t meta-backend .
```

Ejecutar contenedor:

```bash
docker run --rm -p 8000:8000 --env-file backend/.env meta-backend
```

## Frontend

1. Instalar dependencias:

```bash
cd frontend
npm install
```

2. Configurar entorno:

```bash
cp .env.example .env
```

3. Ejecutar app:

```bash
npm run dev
```

## Flujo

1. Crear configuraciones (nombre, BM ID, token) en la pagina **Configuracion**.
2. En **Campanas**, seleccionar configuracion y cargar cuentas/campanas.
3. Lanzar clonacion bulk o single.
4. Revisar jobs, logs y cancelar si es necesario.

## Endpoints principales

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
