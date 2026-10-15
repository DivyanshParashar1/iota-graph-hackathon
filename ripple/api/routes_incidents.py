"""Scenarios and incidents: trigger (background orchestrator), list, detail, SSE timeline, graph, close."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ripple.agents.events import BUS
from ripple.agents.orchestrator import Orchestrator, effective_mode, prepare
from ripple.api.deps import scope_dep, tool_error
from ripple.db import TenantScope, now_ms
from ripple.scenarios import load_scenarios, scenario_event
from ripple.tools.actions import list_actions
from ripple.tools.base import ToolError, call_context, dedupe
from ripple.tools.impact import _highlight, get_incident
from ripple.tools.memory import close_incident

router = APIRouter(prefix="/api")


class IncidentIn(BaseModel):
    scenario_id: str | None = None
    event: dict | None = None
    mode: str | None = None


@router.get("/scenarios")
def scenarios(scope: TenantScope = Depends(scope_dep)):
    return [{"id": sid, "name": sc["name"], "description": sc.get("description", ""),
             "event": scenario_event(sid, scope.tenant_id)} for sid, sc in load_scenarios().items()]


@router.post("/incidents")
def create_incident(body: IncidentIn, request: Request, scope: TenantScope = Depends(scope_dep)):
    if body.scenario_id:
        if body.scenario_id not in load_scenarios():
            raise HTTPException(404, f"unknown scenario {body.scenario_id}")
        event = scenario_event(body.scenario_id, scope.tenant_id)
    elif body.event:
        event = dict(body.event)
    else:
        raise HTTPException(422, "scenario_id or event is required")
    try:
        _, iid = prepare(scope, event)
    except ToolError as e:
        raise tool_error(e) from e
    existing = get_incident(scope, iid)
    if existing and existing["incident"].get("status") == "closed":
        event["started_at"] = now_ms()  # a new occurrence of a closed scenario is a new incident
    mode = body.mode or request.app.state.settings.ripple_agent_mode
    orch = Orchestrator(scope, mode)
    iid, _ = orch.start(event)
    request.app.state.started.add(iid)
    return {"incident_id": iid, "mode": orch.mode_label, "event": event}


@router.get("/incidents")
def incidents(scope: TenantScope = Depends(scope_dep)):
    return scope.ops.run("incidents_list", {"limit": 100})


def _episodes(scope: TenantScope, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    allep = {e["id"]: e for e in scope.mem.run("episodes_all", {})}
    return [allep[i] for i in ids if i in allep]


@router.get("/incidents/{iid}")
def incident(iid: str, scope: TenantScope = Depends(scope_dep)):
    inc = get_incident(scope, iid)
    if not inc:
        raise HTTPException(404, f"unknown incident {iid}")
    i = inc["incident"]
    pb = None
    if i.get("playbook_id"):
        pb = next((p for p in scope.mem.run("playbooks_list", {}) if p["id"] == i["playbook_id"]), None)
    return {**inc, "actions": list_actions(scope, incident_id=iid),
            "handoffs": scope.ops.run("incident_handoffs", {"iid": iid}),
            "recalled": _episodes(scope, i.get("recalled_episodes") or []), "playbook": pb,
            "running": not BUS.is_done(iid) and bool(BUS.history(iid))}


def _loads(s: str | None) -> dict:
    try:
        return json.loads(s or "{}")
    except ValueError:
        return {"raw": (s or "")[:500]}


def _replay_from_graph(scope: TenantScope, iid: str) -> list[dict]:
    """After a restart the in-memory bus is empty: rebuild a timeline from the logged ToolCalls."""
    out = []
    for n, t in enumerate(scope.ops.run("incident_tool_calls", {"iid": iid}), start=1):
        out.append({"seq": n, "ts": t["ts"], "incident_id": iid, "agent": t["agent"], "kind": "tool_result",
                    "tool": t["tool"], "args": _loads(t["args_json"]),
                    "summary": f"{t['tool']} ({t['ms']} ms, {t['n_nodes']} nodes) [replayed from graph]",
                    "node_ids": [], "edges": [], "data": None})
    inc = get_incident(scope, iid)
    out.append({"seq": len(out) + 1, "ts": now_ms(), "incident_id": iid, "agent": "comms", "kind": "done",
                "tool": None, "args": {}, "summary": (inc or {}).get("incident", {}).get("summary") or "replayed",
                "node_ids": [iid], "edges": [], "data": {"replayed": True}})
    return out


@router.get("/incidents/{iid}/events")
async def events(iid: str, request: Request, scope: TenantScope = Depends(scope_dep)):
    if not BUS.history(iid) and iid not in request.app.state.started:
        if not get_incident(scope, iid):
            raise HTTPException(404, f"unknown incident {iid}")
        if True:
            replay = _replay_from_graph(scope, iid)

            async def gen_replay():
                for ev in replay:
                    yield {"data": json.dumps(ev, default=str)}

            return EventSourceResponse(gen_replay())

    async def gen():
        async for ev in BUS.stream(iid):
            if await request.is_disconnected():
                break
            yield {"data": json.dumps(ev, default=str)}

    return EventSourceResponse(gen())


@router.get("/incidents/{iid}/graph")
def incident_graph(iid: str, scope: TenantScope = Depends(scope_dep)):
    inc = get_incident(scope, iid)
    if not inc:
        raise HTTPException(404, f"unknown incident {iid}")
    nodes: list[str] = []
    edges: list[tuple] = []
    for ev in BUS.history(iid):
        if ev["kind"] == "tool_result" and ev["tool"] in ("blast_radius", "alt_route", "who_owns", "contract_terms",
                                                           "propose_action", "recall_similar_episodes"):
            nodes += ev["node_ids"]
            edges += [tuple(e) for e in ev["edges"]]
    if not nodes:
        with call_context(no_log=True):
            nodes, edges = _highlight(scope, inc["disruption"]["type"], inc["disruption"]["id"],
                                      inc["incident"].get("parts_impacted") or [])
        nodes = [iid, inc["disruption"]["id"]] + nodes
        edges = [(inc["disruption"]["id"], "TRIGGERED", iid)] + list(edges)
    for a in scope.ops.run("action_evidence_edges", {"iid": iid}):
        nodes += [a["action"]] + a["evidence"]
        edges += [(a["action"], "FOR_INCIDENT", iid)] + [(a["action"], "BASED_ON", e) for e in a["evidence"]]
    nodes = [n for n in dedupe([iid] + nodes) if isinstance(n, str) and not n.startswith("CARRIER:")][:300]
    info = {r["id"]: r for r in scope.ops.run("nodes_exist", {"ids": nodes})}
    keep = [n for n in nodes if info.get(n, {}).get("exists")]
    ks = set(keep)
    links = [{"source": a, "target": b, "type": t} for a, t, b in dedupe(edges) if a in ks and b in ks]
    return {"nodes": [{"id": n, "label": info[n]["label"], "name": info[n]["name"]} for n in keep], "links": links}


@router.post("/incidents/{iid}/close")
def close(iid: str, scope: TenantScope = Depends(scope_dep)):
    try:
        with call_context(agent="api", incident_id=iid):
            return close_incident(scope, incident_id=iid).to_dict()
    except ToolError as e:
        raise tool_error(e) from e


@router.get("/mode")
def mode(request: Request):
    return {"default": request.app.state.settings.ripple_agent_mode, "llm": effective_mode("llm")[1]}
