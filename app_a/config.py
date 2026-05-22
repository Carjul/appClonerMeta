import os
from pathlib import Path
from dotenv import load_dotenv

# Carga el .env unificado en la raíz del proyecto
# parents[1] = app_a/../  →  raíz del proyecto
_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

FB_ACCESS_TOKEN       = os.getenv("FB_ACCESS_TOKEN", "")
FB_API_VERSION        = os.getenv("FB_API_VERSION", "v21.0")
PUBLIC_BASE_URL       = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
SESSION_SECRET        = os.getenv("SESSION_SECRET") or os.getenv("APP_A_SECRET_KEY", "dev-secret-change-me")
MONGODB_URI           = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI", "")
MONGODB_DB            = os.getenv("MONGODB_DB_NAME") or os.getenv("MONGODB_DB", "fb_catalog_dashboard")
TRICK_RUNNER_INTERVAL = int(os.getenv("TRICK_RUNNER_INTERVAL", "3600"))

FB_GRAPH_BASE = f"https://graph.facebook.com/{FB_API_VERSION}"
