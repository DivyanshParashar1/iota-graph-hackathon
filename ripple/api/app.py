"""FastAPI app: the API process owns the (embedded) DB; the UI talks only to the API.

    uvicorn ripple.api.app:app --reload            # dev (UI: cd ui && npm run dev)
In production the app also serves ui/dist at / (single container).

v2 boots to an empty database. There is no dataset to build and no tenant until a company starts onboarding -
`POST /api/onboarding/start` creates the tenant, its two graphs and its platform indexes.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ripple import ROOT
from ripple.config import Settings, get_settings
from ripple.db import DB, get_db

log = logging.getLogger("ripple.api")
UI_DIST = ROOT / "ui" / "dist"


def create_app(settings: Settings | None = None, db: DB | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owned = db is None
        app.state.db = db or get_db(settings=settings)
        log.info("ripple up: db=%s tenants=%s provider=%s", app.state.db.mode,
                 app.state.db.list_tenants(), settings.llm_provider)
        yield
        app.state.db.save()
        if owned:
            app.state.db.close()

    app = FastAPI(title="Ripple", version="2.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.api_cors_origins.split(",")],
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    from ripple.api import routes_experts, routes_incidents, routes_meta, routes_onboarding, routes_ontology

    for r in (routes_meta.router, routes_onboarding.router, routes_ontology.router, routes_experts.router,
              routes_incidents.router):
        app.include_router(r)
    if UI_DIST.exists():
        app.mount("/assets", StaticFiles(directory=UI_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            f = UI_DIST / path
            if path and f.is_file() and UI_DIST in f.resolve().parents:
                return FileResponse(f)
            # index.html names the hashed bundle: never cache it, or a rebuilt UI keeps loading the old bundle
            return FileResponse(UI_DIST / "index.html", headers={"Cache-Control": "no-cache"})
    return app


app = create_app()
