"""
core/config.py
──────────────
Configuración unificada para la plataforma.
Lee variables de un único .env en la raíz del proyecto.

Migración desde app_b/config.py:
  · Todas las variables de App B siguen funcionando exactamente igual.
  · Se añaden ALLOWED_ORIGINS y APP_A_* para la integración con Jinja2.
  · Usa Pydantic v2 (BaseSettings).

Instalar si no está:
    pip install pydantic-settings
"""

import json
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Servidor ─────────────────────────────────────────────────
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_URL: str = "http://localhost:8000"

    # ── CORS ─────────────────────────────────────────────────────
    # Dev:  ALLOWED_ORIGINS=["*"]
    # Prod: ALLOWED_ORIGINS=["https://mi-dominio.com"]
    ALLOWED_ORIGINS: List[str] = ["*"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                return json.loads(value)
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    # ── MongoDB ───────────────────────────────────────────────────
    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "meta_automation"

    # ── Subprocesos ───────────────────────────────────────────────
    PYTHON_BIN: str = "python"

    # ── Scheduler ─────────────────────────────────────────────────
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_TZ: str = "America/Bogota"
    SCHEDULER_HOUR: int = 6
    SCHEDULER_MINUTE: int = 0
    SCHEDULER_POLL_SECONDS: int = 30
    SCHEDULER_MAX_CONFIGS: int = 2
    SCHEDULER_CONFIG_IDS: str = ""
    SCHEDULER_CONFIG_NAMES: str = ""
    SCHEDULER_RUN_EXPLORER: bool = True
    SCHEDULER_RUN_DAILY_REPORT: bool = True
    SCHEDULER_INTRADAY_ENABLED: bool = True
    SCHEDULER_INTRADAY_START_HOUR: int = 9
    SCHEDULER_INTRADAY_STOP_HOUR: int = 20
    SCHEDULER_INTRADAY_INTERVAL_MINUTES: int = 120

    # ── FB Catalog Runners ────────────────────────────────────────
    FB_CATALOG_TRICK_RUNNER_ENABLED: bool = True
    FB_CATALOG_TRICK_RUNNER_INTERVAL_SECONDS: int = 3600
    FB_CATALOG_PLANNING_RUNNER_ENABLED: bool = True
    FB_CATALOG_PLANNING_RUNNER_INTERVAL_SECONDS: int = 60

    # ── App A (Jinja2) ────────────────────────────────────────────
    APP_A_SECRET_KEY: str = "cambia-esto-en-produccion"
    APP_A_DEBUG: bool = False


# Singleton
settings = Settings()
