"""
app_b/config.py
───────────────
Wrapper de compatibilidad: expone las mismas constantes de siempre
pero delegando a core.config.settings (fuente única de verdad).

Todos los módulos de app_b que hagan:
    from backend.api.config import MONGO_URI
    from backend.api.config import SCHEDULER_ENABLED
    ...
siguen funcionando sin modificar nada.
"""

from backend.core.config import settings

# ── Servidor ─────────────────────────────────────────────────────
APP_URL  = settings.APP_URL
APP_HOST = settings.APP_HOST
APP_PORT = settings.APP_PORT

# ── MongoDB ───────────────────────────────────────────────────────
MONGO_URI = settings.MONGO_URI
DB_NAME   = settings.DB_NAME

# ── Subprocesos ───────────────────────────────────────────────────
PYTHON_BIN = settings.PYTHON_BIN

# ── Scheduler ─────────────────────────────────────────────────────
SCHEDULER_ENABLED                  = settings.SCHEDULER_ENABLED
SCHEDULER_TZ                       = settings.SCHEDULER_TZ
SCHEDULER_HOUR                     = settings.SCHEDULER_HOUR
SCHEDULER_MINUTE                   = settings.SCHEDULER_MINUTE
SCHEDULER_POLL_SECONDS             = settings.SCHEDULER_POLL_SECONDS
SCHEDULER_MAX_CONFIGS              = settings.SCHEDULER_MAX_CONFIGS
SCHEDULER_CONFIG_IDS               = [v.strip() for v in settings.SCHEDULER_CONFIG_IDS.split(",") if v.strip()]
SCHEDULER_CONFIG_NAMES             = [v.strip() for v in settings.SCHEDULER_CONFIG_NAMES.split(",") if v.strip()]
SCHEDULER_RUN_EXPLORER             = settings.SCHEDULER_RUN_EXPLORER
SCHEDULER_RUN_DAILY_REPORT         = settings.SCHEDULER_RUN_DAILY_REPORT
SCHEDULER_INTRADAY_ENABLED         = settings.SCHEDULER_INTRADAY_ENABLED
SCHEDULER_INTRADAY_START_HOUR      = settings.SCHEDULER_INTRADAY_START_HOUR
SCHEDULER_INTRADAY_STOP_HOUR       = settings.SCHEDULER_INTRADAY_STOP_HOUR
SCHEDULER_INTRADAY_INTERVAL_MINUTES= settings.SCHEDULER_INTRADAY_INTERVAL_MINUTES

# ── FB Catalog Runners ────────────────────────────────────────────
FB_CATALOG_TRICK_RUNNER_ENABLED              = settings.FB_CATALOG_TRICK_RUNNER_ENABLED
FB_CATALOG_TRICK_RUNNER_INTERVAL_SECONDS     = settings.FB_CATALOG_TRICK_RUNNER_INTERVAL_SECONDS
FB_CATALOG_PLANNING_RUNNER_ENABLED           = settings.FB_CATALOG_PLANNING_RUNNER_ENABLED
FB_CATALOG_PLANNING_RUNNER_INTERVAL_SECONDS  = settings.FB_CATALOG_PLANNING_RUNNER_INTERVAL_SECONDS
