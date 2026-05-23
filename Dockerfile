# ── Stage 1: Build React ─────────────────────────────────────────
FROM node:20-alpine AS frontend_builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
# base:"/" en vite.config.js → assets en /assets/, out en backend/api/static/
RUN npm run build

# ── Stage 2: Python + FastAPI ─────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instala dependencias del backend unificado
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copia el proyecto completo
COPY . .

# Sobreescribe backend/api/static/ con el build fresco de React
COPY --from=frontend_builder /app/backend/api/static ./backend/api/static

EXPOSE 8000

# Punto de entrada unificado
CMD ["sh", "-c", "python -m uvicorn backend.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
