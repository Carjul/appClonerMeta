import os
from pathlib import Path
from dotenv import load_dotenv

# Carga .env local en desarrollo (si existe).
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "mongodb://localhost:27017"
DB_NAME = os.getenv("DB_NAME", "meta_automation")
PYTHON_BIN = os.getenv("PYTHON_BIN", "python")
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("PORT") or os.getenv("APP_PORT", "8000"))
