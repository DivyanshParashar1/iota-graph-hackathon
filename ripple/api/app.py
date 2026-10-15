"""FastAPI app: the API process owns the (embedded) DB; the UI talks only to the API.

    uvicorn ripple.api.app:app --reload            # dev (UI: cd ui && npm run dev)
In production the app also serves ui/dist at / (single container).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ripple import ROOT
from ripple.config import TENANTS, Settings, get_settings
from ripple.db import DB, TenantScope, get_db

log = logging.getLogger("ripple.api")
UI_DIST = ROOT / "ui" / "dist"


def create_app(settings: Settings | None = None, db: DB | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owned = db is None
        app.state.db = db or get_db(settings=settings)
        from ripple.graph.schema import apply_schema
        from ripple.ingest.build import build_tenant, is_built
        from ripple.tools.algos import warm_caches

        for t in TENANTS:
            s = TenantScope(t, app.state.db)
            if not is_built(app.state.db, t):
                if settings.ripple_autobuild:
                    log.warning("building tenant %s (sample=%s)", t, settings.ripple_sample_orders)
                    build_tenant(s, settings.ripple_sample_orders if t == "dataco" else None)
                else:
                    apply_schema(s)
            try:
                warm_caches(s)
            except Exception:  # noqa: BLE001 - an empty tenant has nothing to warm
                pass
        yield
        app.state.db.save()
        if owned:
            app.state.db.close()

    app = FastAPI(title="Ripple", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.started = set()  # incident ids whose orchestrator run was started by this process
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.api_cors_origins.split(",")],
                       allow_methods=["*"], allow_headers=["*"])
    from ripple.api import routes_actions, routes_brain, routes_incidents, routes_meta

    for r in (routes_meta.router, routes_incidents.router, routes_actions.router, routes_brain.router):
        app.include_router(r)
    if UI_DIST.exists():
        app.mount("/assets", StaticFiles(directory=UI_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            f = UI_DIST / path
            if path and f.is_file() and UI_DIST in f.resolve().parents:
                return FileResponse(f)
            return FileResponse(UI_DIST / "index.html")
    return app


app = create_app()
