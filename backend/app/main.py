"""Legacy compatibility entrypoint.

Canonical server entrypoint is `backend.main:app`.
This wrapper keeps older commands like `cd backend && uvicorn app.main:app` working.
"""

from pathlib import Path
import sys

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.main import app
