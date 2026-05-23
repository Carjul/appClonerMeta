"""Compatibility entrypoint.

Canonical server entrypoint is `backend.main:app`.
This file remains so old commands like `uvicorn main:app` still work.
"""

from backend.main import app
