"""Serve the built React app from the same process as the API.

In the Docker image the Vite build (``frontend/dist``) is copied in and
``FRONTEND_DIST`` points at it. Locally the Vite dev server serves the
frontend instead, so this is off unless that variable is set.

- ``/assets/*`` are Vite's content-hashed files, so they are cached for a year.
- Other files in the build root (``favicon.svg``) are served as they are.
- Any other GET that no route handles returns ``index.html`` so deep links such
  as ``/t/<id>`` load the app, which then routes on the client (including its
  own not-found page). ``index.html`` is never cached, so a deploy takes
  effect on the next page load.
- ``/api/*`` never falls back to the app: unknown API paths keep FastAPI's
  JSON 404, and wrong methods keep their 405.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import Scope

ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable"
NO_CACHE = "no-cache"

# Paths that belong to the backend and must never be answered with index.html.
BACKEND_PREFIXES = ("/api", "/assets", "/docs", "/redoc", "/openapi.json")


class HashedAssets(StaticFiles):
    """StaticFiles for Vite's hashed output, marked as cacheable forever."""

    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = ASSET_CACHE_CONTROL
        return response


def _is_backend_path(path: str) -> bool:
    return any(
        path == prefix or path.startswith(prefix + "/") for prefix in BACKEND_PREFIXES
    )


def _root_file(dist: Path, path: str) -> Path | None:
    """A file directly in the build root, such as /favicon.svg, if it exists."""
    name = path.lstrip("/")
    if not name or "/" in name or name.startswith("."):
        return None
    candidate = dist / name
    return candidate if candidate.is_file() else None


def install_spa(app: FastAPI, dist: Path) -> None:
    dist = dist.resolve()
    index = dist / "index.html"
    if not index.is_file():
        raise RuntimeError(f"FRONTEND_DIST is set but {index} does not exist")

    if (dist / "assets").is_dir():
        app.mount("/assets", HashedAssets(directory=dist / "assets"), name="assets")

    # A fallback route would also catch GETs to API paths that only allow other
    # methods (turning a 405 into the app's HTML), so the fallback hooks the
    # router's 404 instead and leaves every other error alone.
    @app.exception_handler(StarletteHTTPException)
    async def spa_fallback(request: Request, exc: StarletteHTTPException):
        path = request.url.path
        if (
            exc.status_code != 404
            or request.method not in ("GET", "HEAD")
            or _is_backend_path(path)
        ):
            return await http_exception_handler(request, exc)
        file = _root_file(dist, path)
        if file is not None and file != index:
            return FileResponse(file, headers={"Cache-Control": NO_CACHE})
        return FileResponse(index, headers={"Cache-Control": NO_CACHE})
