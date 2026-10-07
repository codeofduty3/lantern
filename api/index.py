"""Vercel serverless entry point for the LANTERN API.

Vercel's Python runtime serves an ASGI application exported as ``app`` from a
file under ``api/``. We re-export the FastAPI app from ``src.api.main`` and add
a thin middleware so the original request path survives Vercel's rewrite into
``/api/index.py`` (otherwise FastAPI would only ever see that one route).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.main import app as _fastapi_app  # noqa: E402

_ORIGINAL_PATH_HEADERS = (b"x-vercel-original-path", b"x-forwarded-uri", b"x-now-route-matches")


class _RestorePath:
    """Give FastAPI the caller's real path, not Vercel's rewritten one."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            headers = {k.lower(): v for k, v in scope.get("headers") or []}
            original = next((headers[h] for h in _ORIGINAL_PATH_HEADERS if h in headers), None)
            path = (original or scope.get("path", "/").encode()).decode()
            if "?" in path:
                path = path.split("?", 1)[0]
            # Requests arriving through the /api rewrite keep a leading "/api".
            if path.startswith("/api/index"):
                path = path[len("/api/index"):] or "/"
            elif path.startswith("/api/"):
                path = path[len("/api"):]
            scope = {**scope, "path": path, "raw_path": path.encode()}
        await self.app(scope, receive, send)


app = _RestorePath(_fastapi_app)
