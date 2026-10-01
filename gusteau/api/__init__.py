"""HTTP API: `create_app` wires the routers, shared services and the built frontend."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..mercadona import Mercadona
from ..store import Store
from . import plans, recipes, settings, shopping, stats

STATIC = Path(__file__).resolve().parent.parent / "static"


def create_app(store: Store | None = None, static_dir: Path | None = None, shop: Mercadona | None = None) -> FastAPI:
    store = store or Store()
    app = FastAPI(title="Gusteau", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.store = store
    app.state.shop = shop or Mercadona(store.root / ".cache" / "mercadona.json", store.settings()["warehouse"])

    for module in (recipes, plans, shopping, stats, settings):
        app.include_router(module.router, prefix="/api")

    _mount_frontend(app, static_dir or Path(os.environ.get("GUSTEAU_STATIC", STATIC)))
    return app


def _mount_frontend(app: FastAPI, static_dir: Path) -> None:
    """Serve the built SPA: real files as-is, every other non-API path gets index.html."""
    if not static_dir.is_dir():
        return
    root = static_dir.resolve()
    app.mount("/assets", StaticFiles(directory=root / "assets", check_dir=False), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        file = (root / path).resolve()
        if path and file.is_file() and root in file.parents:
            return FileResponse(file)
        return FileResponse(root / "index.html")
