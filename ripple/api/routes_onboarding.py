"""The onboarding API: start, resume, chat, forms, uploads, stage jumps and the live stream.

Agent turns are synchronous on purpose. A turn is one LLM call and the UI is waiting for its reply; the live
stream carries the steps while it runs, so the user sees the agent working rather than a spinner. Everything
the turn writes is in FalkorDB before the response is returned, so a reload can never land between the two.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ripple.api.deps import COOKIE, scope_dep
from ripple.config import get_settings
from ripple.db import TenantScope
from ripple.llm.base import LLMError, get_client
from ripple.onboarding import session as sess
from ripple.onboarding.agents import data_agent
from ripple.onboarding.attachments import UnsupportedUpload, ingest
from ripple.onboarding.events import BUS, StepEmitter
from ripple.onboarding.models import Message
from ripple.onboarding.store import (
    append_message,
    get_form,
    get_session,
    list_answers,
    set_form_status,
)

router = APIRouter(prefix="/api/onboarding")


class StartBody(BaseModel):
    company: str
    industry: str = ""
    tenant_id: str | None = None


class MessageBody(BaseModel):
    text: str


class GotoBody(BaseModel):
    stage: str
    note: str = ""


class AnswersBody(BaseModel):
    values: dict = {}
    confidences: dict = {}
    source: str = "user"


def _sid(scope: TenantScope) -> str:
    s = get_session(scope)
    if not s:
        raise HTTPException(409, "this tenant has no onboarding session")
    return s["id"]


@router.post("/start")
def start(body: StartBody, request: Request, response: Response):
    """Create the tenant, its graphs and its session, and run the interviewer's opening turn."""
    if not body.company.strip():
        raise HTTPException(400, "company is required")
    try:
        scope = sess.start(request.app.state.db, body.company.strip(), body.industry.strip(), body.tenant_id)
    except LLMError as e:
        raise HTTPException(503, str(e)) from None
    response.set_cookie(COOKIE, scope.tenant_id, max_age=60 * 60 * 24 * 365, samesite="lax")
    out = sess.state(scope)
    out["tenant_id"] = scope.tenant_id
    return out


@router.get("/session")
def get_state(scope: TenantScope = Depends(scope_dep)):
    """Full resumable state: stage, thread, open form with its partial values, artifacts, staleness."""
    return sess.state(scope)


@router.post("/message")
def post_message(body: MessageBody, scope: TenantScope = Depends(scope_dep)):
    """A user turn. Runs the current stage's agent and returns the messages it produced."""
    if not body.text.strip():
        raise HTTPException(400, "text is required")
    try:
        msgs = sess.run_turn(scope, _sid(scope), body.text.strip())
    except sess.StageError as e:
        raise HTTPException(409, str(e)) from None
    return {"messages": [m.model_dump() for m in msgs], "state": sess.state(scope)}


@router.post("/resume")
def resume(scope: TenantScope = Depends(scope_dep)):
    """Re-issue a turn that was in flight when the browser or the process went away."""
    msgs = sess.resume_pending(scope)
    return {"messages": [m.model_dump() for m in msgs], "state": sess.state(scope)}


@router.post("/goto")
def goto(body: GotoBody, scope: TenantScope = Depends(scope_dep)):
    """Jump to a stage already reached. Downstream artifacts are flagged stale."""
    try:
        out = sess.goto(scope, body.stage, note=body.note)
    except sess.StageError as e:
        raise HTTPException(400, str(e)) from None
    return {**out, "state": sess.state(scope)}


@router.post("/reonboard")
def reonboard(body: GotoBody | None = None, scope: TenantScope = Depends(scope_dep)):
    """Run onboarding again on a live tenant, starting from its existing brief and ontology."""
    try:
        out = sess.reonboard(scope, note=(body.note if body else ""))
    except sess.StageError as e:
        raise HTTPException(400, str(e)) from None
    return {**out, "state": sess.state(scope)}


# --------------------------------------------------------------------------- forms

@router.post("/forms/{form_id}/answers")
def save_answers(form_id: str, body: AnswersBody, scope: TenantScope = Depends(scope_dep)):
    """Partial save (the UI autosaves per field). Values are coerced to the field's type."""
    form = get_form(scope, form_id)
    if form is None:
        raise HTTPException(404, f"no form {form_id}")
    try:
        saved = data_agent.save_values(scope, form, body.values, source=body.source,
                                       confidences=body.confidences)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {"saved": [a.model_dump() for a in saved],
            "answers": [a.model_dump() for a in list_answers(scope, form_id)]}


@router.post("/forms/{form_id}/submit")
def submit_form(form_id: str, body: AnswersBody | None = None, scope: TenantScope = Depends(scope_dep)):
    """Submit a form round: save any last values, close it, and run the data agent's next turn."""
    form = get_form(scope, form_id)
    if form is None:
        raise HTTPException(404, f"no form {form_id}")
    if body and body.values:
        try:
            data_agent.save_values(scope, form, body.values, source=body.source,
                                    confidences=body.confidences)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
    answers = {a.field_id: a.value for a in list_answers(scope, form_id)}
    missing = data_agent.missing_required(form, answers)
    if missing:
        raise HTTPException(400, f"required fields still empty: {', '.join(missing)}")
    set_form_status(scope, form_id, "submitted")
    sid = _sid(scope)
    append_message(scope, sid, Message(role="user", stage="data", kind="form",
                                        text=f"Submitted {form.title}.",
                                        payload={"form_id": form_id, "answers": answers}))
    msgs = sess.run_turn(scope, sid, None)
    return {"messages": [m.model_dump() for m in msgs], "state": sess.state(scope)}


@router.post("/forms/{form_id}/synthesize")
def synthesize(form_id: str, scope: TenantScope = Depends(scope_dep)):
    """Demo only: autofill the whole form with plausible values, every one flagged synthetic."""
    form = get_form(scope, form_id)
    if form is None:
        raise HTTPException(404, f"no form {form_id}")
    emit = StepEmitter(scope, "data", "synthesize")
    try:
        saved = data_agent.synthesize(scope, form, get_client(), emit)
    except LLMError as e:
        raise HTTPException(503, str(e)) from None
    return {"saved": [a.model_dump() for a in saved], "synthetic": True,
            "answers": [a.model_dump() for a in list_answers(scope, form_id)]}


# --------------------------------------------------------------------------- uploads

@router.post("/attachments")
async def upload(request: Request, file: UploadFile = File(...), note: str = Form(default=""),
                 scope: TenantScope = Depends(scope_dep)):
    """Upload one file. It is parsed and profiled; only the profile and a summary reach the agents."""
    data = await file.read()
    s = get_settings()
    emit = StepEmitter(scope, (get_session(scope) or {}).get("stage", "interview"), "attachments")
    client = None
    try:
        client = get_client()
    except LLMError:
        pass  # a table needs no summary; a document is stored without one
    try:
        row = await asyncio.to_thread(ingest, scope, file.filename or "upload", data, client=client,
                                      max_mb=s.ripple_max_upload_mb)
    except UnsupportedUpload as e:
        raise HTTPException(400, str(e)) from None
    emit("write", f"parsed {row['filename']} ({row['kind']})",
         data={"id": row["id"], "profile": row.get("profile")})
    sid = _sid(scope)
    append_message(scope, sid, Message(role="user", stage=(get_session(scope) or {}).get("stage", "interview"),
                                        kind="attachment", text=row["filename"],
                                        payload={"attachment_id": row["id"], "kind": row["kind"],
                                                 "note": note}))
    return {"attachment": {k: v for k, v in row.items() if k != "profile"}, "profile": row.get("profile")}


# --------------------------------------------------------------------------- stream

@router.get("/stream")
async def stream(request: Request, after: int = 0, scope: TenantScope = Depends(scope_dep)):
    """SSE of agent steps: history after `after`, then live."""

    async def gen():
        async for ev in BUS.stream(scope.tenant_id, after):
            if await request.is_disconnected():
                return
            yield {"event": "step", "data": json.dumps(ev, default=str)}

    return EventSourceResponse(gen())


@router.get("/steps")
def steps(stage: str = "", limit: int = 200, scope: TenantScope = Depends(scope_dep)):
    """The persisted step trail (the stream's history, rebuilt from the graph after a reconnect)."""
    from ripple.onboarding.store import list_steps

    return {"steps": list_steps(scope, stage, limit)}
