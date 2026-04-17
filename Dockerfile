FROM node:20-alpine AS frontend_builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY . /app
COPY --from=frontend_builder /app/frontend/dist /app/backend/app/static

WORKDIR /app/backend

EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
