"""The incident API: the webhook that starts a run, and the incident views and approvals.

    POST /api/events/{tenant_id}              the webhook. Any JSON object with a free-text `summary`. Needs
                                              `X-Ripple-Webhook-Secret` when RIPPLE_WEBHOOK_SECRET is set.
                                              202 + the incident id; the run happens in a background thread
                                              (`?wait=true` runs it inline and returns the result - tests, CLI).
    POST /api/incidents                       the same, for the current tenant (the UI's "report an event")
    GET  /api/incidents                       list
    GET  /api/incidents/{id}                  everything: artifacts, options with Jev's probabilities, Jev calls,
                                              approvals, and each approved option's live impact
    POST /api/incidents/{id}/options/{oid}/approve | /reject
    POST /api/incidents/{id}/rerun            a fresh run of the same event, as a new incident

Steps stream on the existing `/api/onboarding/stream` with `stage: "incident"`.
"""

from __future__ import annotations

import asyncio
import hmac
import threading

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ripple.api.deps import scope_dep, scope_for
from ripple.db import TenantScope
from ripple.incident import pipeline, store

router = APIRouter()


class NoteBody(BaseModel):
    note: str = ""


def _check_secret(request: Request) -> None:
    secret = request.app.state.settings.ripple_webhook_secret
    if not secret:
        return
    given = request.headers.get("x-ripple-webhook-secret") or ""
    if not hmac.compare_digest(given.encode(), secret.encode()):
        raise HTTPException(401, "bad or missing X-Ripple-Webhook-Secret")


async def _body(request: Request) -> dict:
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, "the event must be JSON") from None
    if not isinstance(body, dict):
        raise HTTPException(400, "the event must be a JSON object")
    return body


def _start(scope: TenantScope, body: dict, wait: bool):
    try:
        inc = pipeline.receive(scope, body)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    if wait:
        pipeline.run(scope, inc["id"])
        return pipeline.detail(scope, inc["id"])
    threading.Thread(target=pipeline.run, args=(scope, inc["id"]), name=f"incident-{inc['id']}",
                     daemon=True).start()
    return JSONResponse({"incident_id": inc["id"], "status": inc["status"]}, status_code=202)


@router.post("/api/events/{tenant_id}")
async def webhook(tenant_id: str, request: Request, wait: bool = False):
    _check_secret(request)
    scope = scope_for(request, tenant_id)
    body = await _body(request)
    return await asyncio.to_thread(_start, scope, body, wait)


@router.post("/api/incidents")
async def report_event(request: Request, wait: bool = False, scope: TenantScope = Depends(scope_dep)):
    return await asyncio.to_thread(_start, scope, await _body(request), wait)


@router.get("/api/incidents")
def list_incidents(limit: int = 50, scope: TenantScope = Depends(scope_dep)):
    return {"incidents": store.list_incidents(scope, max(1, min(limit, 500)))}


@router.get("/api/incidents/{iid}")
def get_incident(iid: str, scope: TenantScope = Depends(scope_dep)):
    try:
        return pipeline.detail(scope, iid)
    except KeyError as e:
        raise HTTPException(404, str(e)) from None


def _act(fn, scope: TenantScope, iid: str, oid: str, note: str):
    try:
        return fn(scope, iid, oid, note=note)
    except KeyError as e:
        raise HTTPException(404, str(e)) from None
    except pipeline.PipelineError as e:
        raise HTTPException(409, str(e)) from None


@router.post("/api/incidents/{iid}/options/{oid}/approve")
def approve(iid: str, oid: str, body: NoteBody | None = None, scope: TenantScope = Depends(scope_dep)):
    return _act(pipeline.approve, scope, iid, oid, (body or NoteBody()).note)


@router.post("/api/incidents/{iid}/options/{oid}/reject")
def reject(iid: str, oid: str, body: NoteBody | None = None, scope: TenantScope = Depends(scope_dep)):
    return _act(pipeline.reject, scope, iid, oid, (body or NoteBody()).note)


@router.post("/api/incidents/{iid}/rerun")
def rerun(iid: str, wait: bool = False, scope: TenantScope = Depends(scope_dep)):
    inc = store.get_incident(scope, iid)
    if inc is None:
        raise HTTPException(404, f"no incident {iid}")
    body = dict(inc.get("raw") or {}) or {"summary": inc["summary"], "kind": inc.get("kind"),
                                          "source": inc.get("source")}
    body.setdefault("summary", inc["summary"])
    return _start(scope, body, wait)
