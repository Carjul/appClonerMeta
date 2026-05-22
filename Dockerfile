# ── Stage 1: Build React (App B) ─────────────────────────────────
FROM node:20-alpine AS frontend_builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
# base:"/" en vite.config.js → assets en /assets/, out en app_b/static/
RUN npm run build

# ── Stage 2: Python + FastAPI ─────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependencias unificadas
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia el proyecto completo
COPY . .

# Sobreescribe app_b/static/ con el build fresco de React
COPY --from=frontend_builder /app/app_b/static ./app_b/static

EXPOSE 8000

# Punto de entrada unificado en la raíz
CMD ["sh", "-c", "python -m uvicorn main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
