"""Action queue and lifecycle (approve / reject / execute / undo) with before/after revenue at risk."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ripple.api.deps import scope_dep, tool_error
from ripple.db import TenantScope
from ripple.tools.actions import (approve_action, execute_action, get_action, list_actions, reject_action,
                                  undo_action)
from ripple.tools.base import ToolError, call_context
from ripple.tools.impact import revenue_at_risk

router = APIRouter(prefix="/api/actions")


class UserIn(BaseModel):
    user: str = "USR-demo"
    user_name: str | None = None
    reason: str = ""
    execute: bool = True


@router.get("")
def actions(status: str | None = None, incident_id: str | None = None, scope: TenantScope = Depends(scope_dep)):
    return list_actions(scope, status=status, incident_id=incident_id)


@router.get("/{aid}")
def action(aid: str, scope: TenantScope = Depends(scope_dep)):
    a = get_action(scope, aid)
    if not a:
        raise HTTPException(404, f"unknown action {aid}")
    a.pop("undo_json", None)
    return a


def _rev(scope: TenantScope, a: dict) -> float | None:
    iid = a.get("incident_id")
    return revenue_at_risk(scope, incident_id=iid).data["revenue_at_risk"] if iid else None


@router.post("/{aid}/approve")
def approve(aid: str, body: UserIn | None = None, scope: TenantScope = Depends(scope_dep)):
    body = body or UserIn()
    a = get_action(scope, aid)
    if not a:
        raise HTTPException(404, f"unknown action {aid}")
    try:
        with call_context(agent="api", incident_id=a.get("incident_id")):
            before = _rev(scope, a)
            r = approve_action(scope, action_id=aid, user=body.user, user_name=body.user_name).data
            ex = execute_action(scope, action_id=aid, agent="planner").data if body.execute else None
            after = _rev(scope, a)
    except ToolError as e:
        raise tool_error(e) from e
    return {**r, "status": get_action(scope, aid)["status"], "revenue_before": before, "revenue_after": after,
            "executed": ex}


@router.post("/{aid}/reject")
def reject(aid: str, body: UserIn | None = None, scope: TenantScope = Depends(scope_dep)):
    body = body or UserIn()
    try:
        return reject_action(scope, action_id=aid, user=body.user, reason=body.reason, user_name=body.user_name).data
    except ToolError as e:
        raise tool_error(e) from e


@router.post("/{aid}/execute")
def execute(aid: str, scope: TenantScope = Depends(scope_dep)):
    try:
        with call_context(agent="api"):
            return execute_action(scope, action_id=aid).data
    except ToolError as e:
        raise tool_error(e) from e


@router.post("/{aid}/undo")
def undo(aid: str, scope: TenantScope = Depends(scope_dep)):
    try:
        with call_context(agent="api"):
            return undo_action(scope, action_id=aid).data
    except ToolError as e:
        raise tool_error(e) from e
