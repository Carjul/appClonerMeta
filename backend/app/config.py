import os
from pathlib import Path
from dotenv import load_dotenv

# Carga .env local en desarrollo (si existe).
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "mongodb://localhost:27017"
DB_NAME = os.getenv("DB_NAME", "meta_automation")
PYTHON_BIN = os.getenv("PYTHON_BIN", "python")
APP_URL = os.getenv("VITE_API_BASE")
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("PORT") or os.getenv("APP_PORT", "8000"))


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SCHEDULER_ENABLED = _as_bool(os.getenv("SCHEDULER_ENABLED"), True)
SCHEDULER_TZ = os.getenv("SCHEDULER_TZ", "America/Bogota")
SCHEDULER_HOUR = int(os.getenv("SCHEDULER_HOUR", "7"))
SCHEDULER_MINUTE = int(os.getenv("SCHEDULER_MINUTE", "30"))
SCHEDULER_POLL_SECONDS = int(os.getenv("SCHEDULER_POLL_SECONDS", "30"))
SCHEDULER_MAX_CONFIGS = int(os.getenv("SCHEDULER_MAX_CONFIGS", "2"))
SCHEDULER_CONFIG_IDS = [v.strip() for v in os.getenv("SCHEDULER_CONFIG_IDS", "").split(",") if v.strip()]
SCHEDULER_CONFIG_NAMES = [v.strip() for v in os.getenv("SCHEDULER_CONFIG_NAMES", "").split(",") if v.strip()]
