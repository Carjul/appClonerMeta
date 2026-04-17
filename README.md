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
En Render puedes usar `MONGO_URI` o `MONGODB_URI` (ambas funcionan).
Ejemplo:

```env
MONGO_URI=mongodb://localhost:27017
DB_NAME=meta_automation
```

Variables recomendadas en Render:

- `MONGO_URI` (o `MONGODB_URI`)
- `DB_NAME`
- `PYTHON_BIN` (opcional)

Render inyecta `PORT` automaticamente; el contenedor ya la usa.

3. Ejecutar API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Frontend embebido en backend

El `Dockerfile` ya compila el frontend automaticamente y lo copia en `backend/app/static`, asi que en Render no necesitas copiar archivos manualmente.

En ejecucion, FastAPI responde la UI en `/` y los assets en `/assets`.

## Docker (backend)

Construir imagen (desde la raiz del proyecto):

```bash
docker build -f Dockerfile -t meta-backend .
```

Ejecutar contenedor:

```bash
docker run --rm -p 8000:8000 --env-file backend/.env meta-backend
```

Para Render (puerto dinamico), no fijes el puerto en el comando del contenedor.
El Dockerfile ya usa `PORT` automaticamente:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
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
