"""The experts API: list, create by hand, edit (including the system prompt), approve, retire, delete, export,
import, and ask a role a question against the tenant's graph.

Approval is per role (plan.md §4.4). Once every generated role has been decided, `POST /api/experts/finish`
closes onboarding.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ripple.api.deps import scope_dep
from ripple.db import TenantScope
from ripple.experts import runtime
from ripple.experts.store import export_all, export_role, import_dir
from ripple.llm.base import LLMError, get_client
from ripple.onboarding import session as sess
from ripple.onboarding.agents.expert_generator import validate_roles
from ripple.onboarding.events import StepEmitter
from ripple.onboarding.models import ExpertRole
from ripple.onboarding.store import (
    approved_spec,
    delete_expert,
    get_expert,
    get_session,
    list_experts,
    save_expert,
    set_expert_status,
)

router = APIRouter(prefix="/api/experts")


class RoleBody(BaseModel):
    role: dict


class AskBody(BaseModel):
    question: str


def _role(scope: TenantScope, expert_id: str) -> ExpertRole:
    role = get_expert(scope, expert_id)
    if role is None:
        raise HTTPException(404, f"no expert {expert_id}")
    return role


@router.get("")
def list_roles(scope: TenantScope = Depends(scope_dep)):
    roles = list_experts(scope)
    spec, _ = approved_spec(scope)
    return {"experts": [r.model_dump() for r in roles],
            "ontology_types": [t.label for t in spec.types] if spec else [],
            "pending": sum(1 for r in roles if r.status == "draft"),
            "approved": sum(1 for r in roles if r.status == "approved")}


@router.post("")
def create_role(body: RoleBody, scope: TenantScope = Depends(scope_dep)):
    """A user-authored role. Validated against the approved ontology, exactly like a generated one."""
    spec, _ = approved_spec(scope)
    if spec is None:
        raise HTTPException(409, "approve an ontology first")
    try:
        role = ExpertRole.model_validate({**body.role, "origin": "user"})
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"that is not an expert role: {e}") from None
    errors = validate_roles([role], spec)
    if errors:
        raise HTTPException(400, {"message": "the role is not valid", "errors": errors})
    saved = save_expert(scope, role.model_copy(update={"id": role.id or f"EXP-{role.name}"}))
    export_role(scope, saved)
    StepEmitter(scope, "experts", "user")("write", f"role {saved.name} created by hand")
    return saved.model_dump()


@router.patch("/{expert_id}")
def edit_role(expert_id: str, body: RoleBody, scope: TenantScope = Depends(scope_dep)):
    """Edit any field of a role, including its system prompt. Bumps the version."""
    cur = _role(scope, expert_id)
    spec, _ = approved_spec(scope)
    try:
        merged = ExpertRole.model_validate({**cur.model_dump(), **body.role, "id": cur.id,
                                            "version": cur.version + 1})
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"that is not an expert role: {e}") from None
    if spec is not None:
        errors = validate_roles([merged], spec)
        if errors:
            raise HTTPException(400, {"message": "the edited role is not valid", "errors": errors})
    saved = save_expert(scope, merged)
    export_role(scope, saved)
    StepEmitter(scope, "experts", "user")("write", f"role {saved.name} edited (v{saved.version})")
    return saved.model_dump()


@router.post("/{expert_id}/approve")
def approve_role(expert_id: str, scope: TenantScope = Depends(scope_dep)):
    role = _role(scope, expert_id)
    set_expert_status(scope, role.id, "approved")
    StepEmitter(scope, "experts", "user")("write", f"role {role.name} approved")
    return list_roles(scope)


@router.post("/{expert_id}/retire")
def retire_role(expert_id: str, scope: TenantScope = Depends(scope_dep)):
    role = _role(scope, expert_id)
    set_expert_status(scope, role.id, "retired")
    StepEmitter(scope, "experts", "user")("write", f"role {role.name} retired")
    return list_roles(scope)


@router.delete("/{expert_id}")
def remove_role(expert_id: str, scope: TenantScope = Depends(scope_dep)):
    role = _role(scope, expert_id)
    delete_expert(scope, role.id)
    StepEmitter(scope, "experts", "user")("write", f"role {role.name} deleted")
    return list_roles(scope)


@router.post("/export")
def export(scope: TenantScope = Depends(scope_dep)):
    """Write every role to `tenants/<id>/experts/*.md`."""
    paths = export_all(scope)
    return {"files": [str(p.relative_to(scope.dir)) for p in paths]}


@router.post("/import")
def import_roles(scope: TenantScope = Depends(scope_dep)):
    """Read `tenants/<id>/experts/*.md` back into the graph (prompts edited in a text editor or in git)."""
    roles = import_dir(scope)
    return {"imported": [r.model_dump() for r in roles]}


@router.post("/{expert_id}/ask")
def ask(expert_id: str, body: AskBody, scope: TenantScope = Depends(scope_dep)):
    """Run this role against the tenant's graph with its own system prompt and its tool allow-list."""
    role = _role(scope, expert_id)
    if not body.question.strip():
        raise HTTPException(400, "question is required")
    emit = StepEmitter(scope, "ready", role.name)
    emit("llm", f"{role.name}: {body.question[:160]}")
    try:
        out = runtime.ask(scope, role, body.question.strip(),
                          client=get_client(),
                          on_step=lambda ev: emit(ev["kind"], ev.get("summary") or ev.get("tool") or "",
                                                  data={k: v for k, v in ev.items()
                                                        if k not in ("kind", "summary")}))
    except LLMError as e:
        raise HTTPException(503, str(e)) from None
    return out


@router.post("/finish")
def finish(scope: TenantScope = Depends(scope_dep)):
    """Close onboarding: the tenant goes live. At least one role has to be approved."""
    roles = list_experts(scope)
    if not any(r.status == "approved" for r in roles):
        raise HTTPException(400, "approve at least one expert role before finishing")
    s = get_session(scope)
    if not s:
        raise HTTPException(409, "no onboarding session")
    if s.get("stage") != "experts":
        raise HTTPException(409, f"onboarding is at the {s.get('stage')} stage, not experts")
    msgs = sess.advance(scope, s["id"], "experts", reason="expert roles approved")
    return {"messages": [m.model_dump() for m in msgs], "state": sess.state(scope)}
