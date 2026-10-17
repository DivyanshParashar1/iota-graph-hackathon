"""Every read and write of incident state in FalkorDB.

An incident is one `_Incident` node holding the event and each stage's artifact as JSON (exchanges, evidence
report, analysis, comms, plan, packet, policy outcome), plus three kinds of child node: `_Option` (one per
proposed option, with Jev's probability and its status), `_JevDecision` (one per Jev call) and `_Approval`
(every approve/reject, by a person or by the policy). `(:_Incident)-[:CONCERNS]->(n)` links it to the instance
nodes its evidence names, so the Graph page can show what an incident touches.
"""

from __future__ import annotations

import json
import time
from typing import Any

from ripple.db import TenantScope, new_id, now_ms
from ripple.incident.models import EventRecord

ARTIFACTS = ("exchanges", "report", "analysis", "comms", "plan", "packet", "outcome", "qmap", "relevant")


def _j(value: Any) -> str:
    return json.dumps(value, default=str)


def _unj(text: Any, default: Any = None) -> Any:
    if text in (None, ""):
        return default
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return default


def create_incident(scope: TenantScope, event: EventRecord) -> dict:
    iid = event.id or new_id("INC")
    ts = now_ms()
    row = {"id": iid, "kind": event.kind, "summary": event.summary, "source": event.source,
           "received_at": event.received_at, "raw_json": _j(event.raw), "status": "received", "priority": "",
           "auto": False, "error": "", "ts": ts, "updated_at": ts}
    scope.ops.run("incident_upsert", {"row": row})
    return get_incident(scope, iid) or row


def set_incident(scope: TenantScope, iid: str, **patch) -> None:
    """Patch an incident. Artifacts (`report=`, `packet=`, ...) are stored as `<name>_json`."""
    row: dict[str, Any] = {"id": iid, "updated_at": now_ms()}
    for k, v in patch.items():
        row[f"{k}_json" if k in ARTIFACTS else k] = _j(v) if k in ARTIFACTS else v
    scope.ops.run("incident_upsert", {"row": row})


def get_incident(scope: TenantScope, iid: str) -> dict | None:
    rows = scope.ops.run("incident_get", {"id": iid})
    if not rows:
        return None
    props = dict(rows[0]["props"])
    out = {k: v for k, v in props.items() if not k.endswith("_json")}
    out["raw"] = _unj(props.get("raw_json"), {})
    for a in ARTIFACTS:
        out[a] = _unj(props.get(f"{a}_json"))
    return out


def event_of(incident: dict) -> EventRecord:
    return EventRecord(id=incident["id"], kind=incident.get("kind") or "event", summary=incident["summary"],
                       source=incident.get("source") or "webhook", received_at=incident.get("received_at") or "",
                       raw=incident.get("raw") or {})


def list_incidents(scope: TenantScope, limit: int = 50) -> list[dict]:
    return scope.ops.run("incidents_list", {"limit": limit})


# --------------------------------------------------------------------------- options

def option_key(iid: str, option_id: str) -> str:
    return f"{iid}:{option_id}"


def save_option(scope: TenantScope, iid: str, *, option: dict, group_id: str, mode: str, probability: float,
                rank: int, status: str, reason: str) -> None:
    scope.ops.run("incident_option_upsert", {"iid": iid, "row": {
        "id": option_key(iid, option["id"]), "incident_id": iid, "option_id": option["id"], "group_id": group_id,
        "mode": mode, "title": option.get("title", ""), "probability": float(probability), "rank": int(rank),
        "status": status, "reason": reason, "data_json": _j(option), "ts": now_ms()}})


def list_options(scope: TenantScope, iid: str) -> list[dict]:
    out = []
    for r in scope.ops.run("incident_options_list", {"iid": iid}):
        p = dict(r["props"])
        p["data"] = _unj(p.pop("data_json", None), {})
        out.append(p)
    return out


def set_option(scope: TenantScope, iid: str, option_id: str, **patch) -> None:
    scope.ops.run("incident_option_set", {"id": option_key(iid, option_id), "patch": patch})


# --------------------------------------------------------------------------- Jev calls and approvals

def record_jev(scope: TenantScope, iid: str, purpose: str, request: dict, result: dict, model: str,
               ms: float) -> str:
    did = new_id("JEV")
    scope.ops.run("jev_decision_append", {"iid": iid, "row": {
        "id": did, "incident_id": iid, "purpose": purpose, "request_json": _j(request), "result_json": _j(result),
        "model": model, "ms": float(ms), "ts": now_ms(), "ns": time.time_ns()}})
    return did


def list_jev(scope: TenantScope, iid: str) -> list[dict]:
    out = []
    for r in scope.ops.run("jev_decisions_list", {"iid": iid}):
        p = dict(r["props"])
        p["request"] = _unj(p.pop("request_json", None), {})
        p["result"] = _unj(p.pop("result_json", None), {})
        out.append(p)
    return out


def record_approval(scope: TenantScope, iid: str, option_id: str, *, actor: str, action: str,
                    note: str = "") -> str:
    aid = new_id("APR")
    scope.ops.run("approval_append", {"iid": iid, "row": {
        "id": aid, "incident_id": iid, "option_key": option_key(iid, option_id), "option_id": option_id,
        "actor": actor, "action": action, "note": note, "ts": now_ms(), "ns": time.time_ns()}})
    return aid


def list_approvals(scope: TenantScope, iid: str) -> list[dict]:
    return [dict(r["props"]) for r in scope.ops.run("approvals_list", {"iid": iid})]


# --------------------------------------------------------------------------- the graph around an incident

def link_concerns(scope: TenantScope, iid: str, node_ids: list[str]) -> int:
    if not node_ids:
        return 0
    rows = scope.ops.run("incident_concerns_link", {"iid": iid, "ids": sorted(set(node_ids))})
    return int(rows[0]["linked"]) if rows else 0


def nodes_by_ids(scope: TenantScope, node_ids: list[str]) -> list[dict]:
    if not node_ids:
        return []
    return scope.ops.run("nodes_by_ids", {"ids": sorted(set(node_ids))})
