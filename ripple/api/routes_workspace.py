"""The workspace API: employees (personas assigned to expert roles), their role dashboards, and their chat with
the orchestrator that deploys the expert agents.

There is no auth (see api/deps.py): choosing an employee is a persona switch that scopes what the dashboard
shows and who the orchestrator is talking to, not an access control boundary.
"""

from __future__ import annotations

import threading

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ripple.api.deps import scope_dep
from ripple.api.routes_overview import concentration_hotspots, status_hotspots
from ripple.db import TenantScope
from ripple.incident.store import list_incidents
from ripple.llm.base import LLMError
from ripple.onboarding.store import approved_spec, instance_counts, list_experts
from ripple.workspace import orchestrator
from ripple.workspace.store import (
    Employee,
    append_chat,
    delete_employee,
    delete_thread,
    get_employee,
    list_chat,
    list_employees,
    list_threads,
    save_employee,
    save_thread,
)

router = APIRouter(prefix="/api/workspace")

_running: set[str] = set()
_lock = threading.Lock()


class EmployeeBody(BaseModel):
    name: str
    title: str = ""
    role_ids: list[str] = Field(default_factory=list)


class ChatBody(BaseModel):
    text: str
    thread_id: str = ""


def _employee(scope: TenantScope, eid: str) -> Employee:
    e = get_employee(scope, eid)
    if e is None:
        raise HTTPException(404, f"no employee {eid}")
    return e


def _check_roles(scope: TenantScope, role_ids: list[str]) -> list[str]:
    known = {r.id for r in list_experts(scope)}
    bad = [r for r in role_ids if r not in known]
    if bad:
        raise HTTPException(400, f"unknown expert roles: {bad}")
    return list(dict.fromkeys(role_ids))


def _thread_of(scope: TenantScope, eid: str, tid: str) -> dict:
    t = next((t for t in list_threads(scope, eid, limit=500) if t["id"] == tid), None)
    if t is None:
        raise HTTPException(404, f"no thread {tid} for {eid}")
    return t


@router.get("/employees")
def employees(scope: TenantScope = Depends(scope_dep)):
    roles = {r.id: r for r in list_experts(scope)}
    return {"employees": [{**e.model_dump(),
                           "roles": [{"id": rid, "title": roles[rid].title, "name": roles[rid].name}
                                     for rid in e.role_ids if rid in roles]} for e in list_employees(scope)]}


@router.post("/employees")
def create_employee(body: EmployeeBody, scope: TenantScope = Depends(scope_dep)):
    if not body.name.strip():
        raise HTTPException(400, "an employee needs a name")
    e = save_employee(scope, Employee(name=body.name.strip(), title=body.title.strip(),
                                      role_ids=_check_roles(scope, body.role_ids)))
    return e.model_dump()


@router.patch("/employees/{eid}")
def edit_employee(eid: str, body: EmployeeBody, scope: TenantScope = Depends(scope_dep)):
    e = _employee(scope, eid)
    e = save_employee(scope, e.model_copy(update={"name": body.name.strip() or e.name, "title": body.title.strip(),
                                                  "role_ids": _check_roles(scope, body.role_ids)}))
    return e.model_dump()


@router.delete("/employees/{eid}")
def remove_employee(eid: str, scope: TenantScope = Depends(scope_dep)):
    _employee(scope, eid)
    delete_employee(scope, eid)
    return {"deleted": eid}


@router.get("/employees/{eid}/dashboard")
def dashboard(eid: str, scope: TenantScope = Depends(scope_dep)):
    """Everything scoped to the employee's roles: their focus types, counts, hot spots, incidents, threads."""
    e = _employee(scope, eid)
    all_roles = {r.id: r for r in list_experts(scope)}
    roles = [all_roles[rid] for rid in e.role_ids if rid in all_roles]
    focus = list(dict.fromkeys(t for r in roles for t in r.focus_types))
    spec, _ = approved_spec(scope)
    counts = instance_counts(scope)
    hot = []
    if spec:
        mine = set(focus)
        hot = [h for h in status_hotspots(scope, spec) + concentration_hotspots(scope, spec)
               if not mine or {h.get("label"), h.get("from"), h.get("to")} & mine]
    return {
        "employee": e.model_dump(),
        "roles": [{"id": r.id, "name": r.name, "title": r.title, "mandate": r.mandate, "status": r.status,
                   "focus_types": r.focus_types, "focus_relationships": r.focus_relationships,
                   "playbook": r.playbook} for r in roles],
        "focus_types": focus,
        "counts": {t: counts["nodes"].get(t, 0) for t in focus},
        "hotspots": hot,
        "incidents": list_incidents(scope, limit=6),
        "experts": [{"id": r.id, "name": r.name, "title": r.title} for r in all_roles.values()
                    if r.status == "approved"],
        "threads": list_threads(scope, eid),
    }


@router.get("/employees/{eid}/threads")
def threads(eid: str, scope: TenantScope = Depends(scope_dep)):
    _employee(scope, eid)
    return {"threads": list_threads(scope, eid)}


class ThreadBody(BaseModel):
    title: str = ""


@router.post("/employees/{eid}/threads")
def new_thread(eid: str, body: ThreadBody | None = None, scope: TenantScope = Depends(scope_dep)):
    """Open an empty thread, so the UI knows its id (and can follow its live trail) before the first answer."""
    _employee(scope, eid)
    return save_thread(scope, eid, title=(body.title.strip() if body else "")[:80] or "New chat")


@router.get("/employees/{eid}/threads/{tid}")
def thread(eid: str, tid: str, scope: TenantScope = Depends(scope_dep)):
    t = _thread_of(scope, eid, tid)
    return {"thread": t, "messages": list_chat(scope, tid), "running": tid in _running}


@router.delete("/employees/{eid}/threads/{tid}")
def remove_thread(eid: str, tid: str, scope: TenantScope = Depends(scope_dep)):
    _thread_of(scope, eid, tid)
    delete_thread(scope, tid)
    return {"deleted": tid}


@router.post("/employees/{eid}/chat")
def chat(eid: str, body: ChatBody, scope: TenantScope = Depends(scope_dep)):
    """One employee message: stored, answered by the orchestrator (which deploys expert agents), stored."""
    e = _employee(scope, eid)
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "empty message")
    t = _thread_of(scope, eid, body.thread_id) if body.thread_id else save_thread(scope, eid, title=text[:80])
    tid = t["id"]
    with _lock:
        if tid in _running:
            raise HTTPException(409, "the orchestrator is still answering in this thread")
        _running.add(tid)
    try:
        history = list_chat(scope, tid)
        if not history and t.get("title") in (None, "", "New chat"):
            save_thread(scope, eid, tid, title=text[:80])
        user = append_chat(scope, tid, "user", text)
        try:
            out = orchestrator.run(scope, e, tid, history, text)
        except ValueError as err:
            raise HTTPException(409, str(err)) from None
        except LLMError as err:
            raise HTTPException(503, str(err)) from None
        reply = append_chat(scope, tid, "assistant", out["text"] or out["reason"],
                            {"ok": out["ok"], "delegations": out["delegations"], "ids": out["ids"],
                             "turns": out["turns"]})
        save_thread(scope, eid, tid)
    finally:
        with _lock:
            _running.discard(tid)
    return {"thread": {**t, "id": tid}, "messages": [user, reply]}
