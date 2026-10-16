"""The stage machine: start, resume, run a turn, jump back, propagate staleness.

Stages run `interview -> data -> ontology -> experts -> ready`. `_Session.stage` is the cursor and FalkorDB is
the only state: every message, checklist edit, form, answer and agent step is written as it happens, so a
reload mid-answer comes back exactly where it was (`state()` is what the UI resumes from).

Who decides a stage is finished:

* **interview** and **data** - the agent does, when its own checklist has nothing material left open. The
  interviewer is additionally blocked by `Brief.core_gaps()`: a core topic that is still empty reopens a
  checklist item instead of closing the stage.
* **ontology** and **experts** - the user does, by approving the spec and the roles. Those live in
  `routes_ontology` / `routes_experts`, which call `advance()` here.

Going back is a first-class move (`goto`): the target stage's agent re-enters with its checklist restored and
every downstream artifact is flagged stale, so the user can see exactly what will need re-approving.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from ripple.config import get_settings
from ripple.db import DB, TenantScope, slug_tenant_id
from ripple.llm.base import LLMError, get_client
from ripple.onboarding import STAGES
from ripple.onboarding.events import BUS, StepEmitter
from ripple.onboarding.models import Message
from ripple.onboarding.store import (
    append_message,
    brief_versions,
    create_session,
    create_tenant,
    current_brief,
    current_spec,
    get_pending,
    get_session,
    get_tenant,
    instance_counts,
    list_answers,
    list_attachments,
    list_checklist,
    list_experts,
    list_forms,
    list_messages,
    list_steps,
    mark_stale,
    open_form,
    set_pending,
    set_session,
    set_tenant,
    spec_versions,
)

# What each stage produces, and what has to be re-derived when it changes.
ARTIFACT_LABELS = {"interview": ["_Brief"], "data": ["_FormSpec", "_FormAnswer"],
                   "ontology": ["_OntologySpec"], "experts": ["_ExpertRole"], "ready": []}
DOWNSTREAM = {
    "interview": ["_FormSpec", "_OntologySpec", "_ExpertRole"],
    "data": ["_OntologySpec", "_ExpertRole"],
    "ontology": ["_ExpertRole"],
    "experts": [],
    "ready": [],
}
AGENT_OF = {"interview": "interviewer", "data": "data_agent", "ontology": "ontologist",
            "experts": "expert_generator", "ready": "ripple"}
log = logging.getLogger("ripple.onboarding")


class StageError(RuntimeError):
    """The stage machine was asked for something the current state does not allow."""


def _agent_module(stage: str):
    from ripple.onboarding.agents import data_agent, expert_generator, interviewer, ontologist

    return {"interview": interviewer, "data": data_agent, "ontology": ontologist,
            "experts": expert_generator}.get(stage)


# --------------------------------------------------------------------------- start / resume

def start(db: DB, company: str, industry: str = "", tenant_id: str | None = None) -> TenantScope:
    """Create the tenant, its graphs and its session, and run the interviewer's opening turn.

    Raises LLMError before creating anything when no provider is configured: a turn that fails mid-session is
    reported in the thread and can be resumed, but a tenant that could never take its first turn is litter."""
    get_client()
    scope = TenantScope(tenant_id or slug_tenant_id(company), db)
    create_tenant(scope, company, industry)
    s = get_settings()
    session = create_session(scope, s.llm_provider or "none", s.model_name)
    opening(scope, session["id"])
    return scope


def opening(scope: TenantScope, sid: str) -> list[Message]:
    """Run the current stage's opening turn (no user text)."""
    return run_turn(scope, sid, user_text=None)


def state(scope: TenantScope) -> dict:
    """Everything the UI needs to resume: stage, thread, open form, artifacts, staleness."""
    tenant = get_tenant(scope) or {}
    session = get_session(scope)
    sid = session["id"] if session else ""
    brief, brief_row = current_brief(scope)
    spec, spec_row = current_spec(scope)
    experts = list_experts(scope)
    form = open_form(scope)
    return {
        "tenant": {**tenant, "stages": list(STAGES)},
        "session": session or {},
        "stage": (session or {}).get("stage") or tenant.get("stage") or "interview",
        "busy": BUS.busy(scope.tenant_id),
        "pending": get_pending(scope),
        "messages": [m.model_dump() for m in (list_messages(scope, sid) if sid else [])],
        "open_form": form.model_dump() if form else None,
        "answers": [a.model_dump() for a in list_answers(scope)],
        "attachments": list_attachments(scope),
        "artifacts": {
            "brief": {**(brief_row or {}), "data": brief.model_dump() if brief else None,
                      "versions": brief_versions(scope)},
            "ontology": {**(spec_row or {}), "data": spec.model_dump(by_alias=True) if spec else None,
                         "versions": spec_versions(scope)},
            "experts": [e.model_dump() for e in experts],
        },
        "counts": instance_counts(scope),
        "progress": progress(scope),
    }


def progress(scope: TenantScope) -> dict:
    """Per-stage progress: reached, open checklist items, artifact status. Drives the stage rail."""
    session = get_session(scope) or {}
    stage = session.get("stage") or "interview"
    reached = STAGES.index(stage) if stage in STAGES else 0
    brief, brief_row = current_brief(scope)
    _, spec_row = current_spec(scope)
    experts = list_experts(scope)
    out = []
    for i, st in enumerate(STAGES):
        items = list_checklist(scope, st) if st != "ready" else []
        artifact: dict = {}
        if st == "interview" and brief_row:
            artifact = {"version": brief_row["version"], "stale": bool(brief_row.get("stale")),
                        "gaps": brief.core_gaps() if brief else []}
        elif st == "data":
            forms = list_forms(scope)
            artifact = {"rounds": len(forms), "answers": len(list_answers(scope)),
                        "open_form": bool(open_form(scope))}
        elif st == "ontology" and spec_row:
            artifact = {"version": spec_row["version"], "status": spec_row["status"],
                        "stale": bool(spec_row.get("stale"))}
        elif st == "experts":
            artifact = {"total": len(experts), "approved": sum(1 for e in experts if e.status == "approved"),
                        "stale": sum(1 for e in experts if e.stale)}
        out.append({"stage": st, "index": i, "reached": i <= reached, "current": st == stage,
                    "open_items": sum(1 for c in items if c.status == "open"),
                    "resolved_items": sum(1 for c in items if c.status == "resolved"), "artifact": artifact})
    return {"stages": out, "stage": stage, "steps": len(list_steps(scope, limit=2000))}


# --------------------------------------------------------------------------- turns

def run_turn(scope: TenantScope, sid: str, user_text: str | None, *,
             on_event: Callable[[dict], None] | None = None) -> list[Message]:
    """One agent turn for the current stage. The user message (when any) is persisted before the LLM call, so a
    crash between the two loses nothing: the pending record re-issues it on resume."""
    session = get_session(scope)
    if not session:
        raise StageError("no session; POST /api/onboarding/start first")
    stage = session.get("stage") or "interview"
    agent = AGENT_OF.get(stage, "ripple")
    emit = StepEmitter(scope, stage, agent)
    if user_text:
        append_message(scope, sid, Message(role="user", stage=stage, kind="text", text=user_text))
    module = _agent_module(stage)
    if module is None:  # "ready": onboarding is over, nothing to run
        return []
    set_pending(scope, sid, {"stage": stage, "user_text": user_text or "", "agent": agent})
    BUS.enter(scope.tenant_id)
    try:
        client = get_client()
        out = module.turn(scope, sid, client, emit)
    except Exception as e:  # noqa: BLE001
        # A failed turn must not cost the session. Everything up to this point is already in FalkorDB, so the
        # failure goes into the thread (and the trail) and the user can answer again or go back a stage.
        # A provider failure is expected; anything else is a bug, and is logged as one.
        fatal = not isinstance(e, LLMError)
        log.exception("%s turn failed", agent) if fatal else log.warning("%s: %s", agent, e)
        emit("error", f"{agent} could not run: {e}", data={"fatal": True, "bug": fatal,
                                                           "error": type(e).__name__})
        msgs = [append_message(scope, sid, Message(
            role="system", stage=stage, kind="system",
            text=f"The {agent} could not run: {e}",
            payload={"error": type(e).__name__, "bug": fatal}))]
        set_pending(scope, sid, None)
        return msgs
    finally:
        BUS.leave(scope.tenant_id)
    set_pending(scope, sid, None)
    messages = out.get("messages") or []
    if out.get("stage_done"):
        messages += advance(scope, sid, stage, reason=out.get("done_reason", ""))
    return messages


def resume_pending(scope: TenantScope) -> list[Message]:
    """Re-issue a turn that was in flight when the process or the browser went away."""
    session = get_session(scope)
    pending = get_pending(scope)
    if not session or not pending:
        return []
    set_pending(scope, session["id"], None)
    return run_turn(scope, session["id"], None)  # the user text is already persisted as a _Message


# --------------------------------------------------------------------------- stage movement

def advance(scope: TenantScope, sid: str, from_stage: str, reason: str = "") -> list[Message]:
    """Move the cursor to the next stage and run that stage's opening turn."""
    i = STAGES.index(from_stage)
    nxt = STAGES[min(i + 1, len(STAGES) - 1)]
    if nxt == from_stage:
        return []
    set_session(scope, sid, stage=nxt)
    set_tenant(scope, stage=nxt, status="live" if nxt == "ready" else "onboarding")
    msgs = [append_message(scope, sid, Message(role="system", stage=nxt, kind="system",
                                               text=f"Stage {from_stage} -> {nxt}."
                                                    + (f" {reason}" if reason else ""),
                                               payload={"from": from_stage, "to": nxt, "reason": reason}))]
    StepEmitter(scope, nxt, AGENT_OF.get(nxt, "ripple"))("stage", f"entered {nxt}")
    if nxt != "ready":
        msgs += run_turn(scope, sid, None)
    return msgs


def goto(scope: TenantScope, stage: str, *, note: str = "") -> dict:
    """Jump to a stage the user has already reached. Downstream artifacts are flagged stale."""
    if stage not in STAGES:
        raise StageError(f"unknown stage {stage!r}")
    session = get_session(scope)
    if not session:
        raise StageError("no session")
    sid = session["id"]
    cur = session.get("stage") or "interview"
    if STAGES.index(stage) > STAGES.index(cur):
        raise StageError(f"stage {stage!r} has not been reached yet (currently {cur!r})")
    flagged = mark_stale(scope, DOWNSTREAM.get(stage, []))
    set_session(scope, sid, stage=stage)
    set_tenant(scope, stage=stage, status="onboarding")
    append_message(scope, sid, Message(role="system", stage=stage, kind="system",
                                       text=f"Back to {stage}." + (f" {note}" if note else ""),
                                       payload={"from": cur, "to": stage, "stale_flagged": flagged,
                                                "downstream": DOWNSTREAM.get(stage, [])}))
    StepEmitter(scope, stage, AGENT_OF.get(stage, "ripple"))(
        "stage", f"jumped back to {stage}; {flagged} downstream artifacts stale",
        data={"downstream": DOWNSTREAM.get(stage, [])})
    return {"stage": stage, "stale_flagged": flagged, "downstream": DOWNSTREAM.get(stage, [])}


def reonboard(scope: TenantScope, note: str = "") -> dict:
    """Run onboarding again on a live tenant: back to the interview, keeping brief, ontology and experts as the
    starting point. New versions are produced; nothing is deleted."""
    session = get_session(scope)
    if not session:
        raise StageError("no session")
    out = goto(scope, "interview", note=note or "Re-onboarding: tell me what changed.")
    set_tenant(scope, status="onboarding")
    msgs = run_turn(scope, session["id"], None)
    return {**out, "messages": [m.model_dump() for m in msgs]}
