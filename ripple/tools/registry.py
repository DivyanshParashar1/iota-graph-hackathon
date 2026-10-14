"""TOOLS: name -> ToolSpec(fn, JSON schema, kind, description). The MCP server, the LLM agents and the API all
read this. Schemas never include a tenant: the tenant comes from the session/scope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ripple.agents import planning
from ripple.tools import actions, algos, brain, impact, memory, sourcing
from ripple.tools.base import ToolResult, logged_tool


@dataclass(frozen=True)
class ToolSpec:
    name: str
    fn: Callable[..., ToolResult]
    kind: str  # read | algo | write | memory
    description: str
    schema: dict

    def anthropic(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.schema}


def S(props: dict, required: list[str] | None = None) -> dict:  # noqa: N802
    return {"type": "object", "properties": props, "required": required or [], "additionalProperties": False}


STR = {"type": "string"}
INT = {"type": "integer"}
NUM = {"type": "number"}
BOOL = {"type": "boolean"}
STRS = {"type": "array", "items": {"type": "string"}}
EVENT = {"type": "object", "description": "Event: {type: port_closure|supplier_failure|carrier_strike, target_name or "
         "target_id, severity?, expected_days?, lat?, lon?, radius_km?, name?}",
         "properties": {"type": {"type": "string", "enum": ["port_closure", "supplier_failure", "carrier_strike"]},
                        "target_name": STR, "target_id": STR, "severity": STR, "expected_days": INT, "lat": NUM,
                        "lon": NUM, "radius_km": NUM, "name": STR, "source": STR, "started_at": INT,
                        "scenario_id": STR},
         "required": ["type"]}


@logged_tool
def plan_reroute(scope, incident_id: str) -> ToolResult:
    """Ready-to-propose REROUTE_ORDERS params for an incident (uses alt_route per impacted lane)."""
    p = planning.plan_reroute(scope, incident_id)
    if not p:
        return ToolResult({"plan": None}, [incident_id], [], [], summary="nothing to reroute")
    return ToolResult({"plan": p}, [incident_id] + p["evidence"], [], ["orders_lanes", "lanes_get", "alt_route"],
                      summary=p["summary"])


@logged_tool
def plan_alt_suppliers(scope, incident_id: str, part_ids: list[str]) -> ToolResult:
    """Ready-to-propose ACTIVATE_ALT_SUPPLIER params: best qualified alternate per impacted part."""
    p = planning.plan_alt_suppliers(scope, incident_id, part_ids)
    if not p:
        return ToolResult({"plan": None}, [incident_id], [], [], summary="no qualified alternates")
    return ToolResult({"plan": p}, [incident_id] + p["evidence"], [], ["alt_suppliers"], summary=p["summary"])


_DEFS = [
    (impact.match_event_to_entities, "read", "Match a disruption event (port/supplier/carrier name or id, or a lat/lon "
     "radius) to RiskBearing nodes in the graph.", S({"event": EVENT}, ["event"])),
    (impact.create_disruption, "write", "Create (MERGE) a Disruption that AFFECTS the matched entity ids.",
     S({"event": EVENT, "entity_ids": STRS}, ["event", "entity_ids"])),
    (impact.open_incident, "write", "Open (MERGE) the Incident blackboard for a disruption. Idempotent.",
     S({"disruption_id": STR, "mode": STR}, ["disruption_id"])),
    (impact.blast_radius, "read", "Multi-hop blast radius of a disruption: open orders, revenue, customers, products, "
     "parts, suppliers, lanes, plus the highlight subgraph. Writes IMPACTS and the incident's numbers.",
     S({"disruption_id": STR, "incident_id": STR, "max_hops": INT})),
    (impact.revenue_at_risk, "read", "Live revenue at risk for an incident (recomputed; drops after reroutes or "
     "supplier switches).", S({"incident_id": STR}, ["incident_id"])),
    (impact.customer_exposure, "read", "Top customers and segments by live revenue at risk.",
     S({"incident_id": STR, "top_k": INT}, ["incident_id"])),
    (impact.late_risk_baseline, "read", "Historical late-delivery rate for a shipping mode and market (DataCo labels).",
     S({"mode": {"type": "string", "enum": ["Standard Class", "Second Class", "First Class", "Same Day"]},
        "market": STR}, ["mode", "market"])),
    (algos.single_points_of_failure, "algo", "Chokepoint suppliers: exact betweenness centrality on SUPPLIES_TO "
     "combined with single-sourced parts downstream.", S({"top_k": INT, "focus_ids": STRS})),
    (algos.supplier_influence, "algo", "PageRank over SUPPLIES_TO: the most depended-on suppliers.", S({"top_k": INT})),
    (algos.supplier_clusters, "algo", "Correlated-risk groups: WCC components and label-propagation communities.",
     S({"top_k": INT})),
    (algos.alt_route, "algo", "Fastest sea route avoiding closed ports (weighted k-shortest paths over CONNECTS); if the "
     "origin is closed, starts from the nearest open port.",
     S({"origin_port": STR, "dest_port": STR, "avoid_ports": STRS, "mode": STR}, ["origin_port", "dest_port"])),
    (sourcing.alt_suppliers, "read", "Qualified alternate suppliers for a part outside a blocked country, excluding "
     "suppliers hit by an active disruption.", S({"part_id": STR, "exclude_country": STR, "limit": INT}, ["part_id"])),
    (sourcing.contract_terms, "read", "A supplier's contract terms and the most relevant clause text; with an incident, "
     "the delay penalty owed (force majeure aware).",
     S({"supplier_id": STR, "clause": STR, "incident_id": STR}, ["supplier_id"])),
    (plan_reroute, "algo", "Ready-made REROUTE_ORDERS params for an incident (groups impacted orders by lane and finds "
     "an alternate lane for each).", S({"incident_id": STR}, ["incident_id"])),
    (plan_alt_suppliers, "read", "Ready-made ACTIVATE_ALT_SUPPLIER params for impacted parts.",
     S({"incident_id": STR, "part_ids": STRS}, ["incident_id", "part_ids"])),
    (actions.propose_action, "write", "Propose an action (REROUTE_ORDERS, ACTIVATE_ALT_SUPPLIER, EXPEDITE, SPLIT_ORDER, "
     "NOTIFY_OWNER, PLACE_HOLD) with the evidence node ids it is based on.",
     S({"incident_id": STR, "type": {"type": "string", "enum": list(actions.ACTION_TYPES)},
        "params": {"type": "object"}, "evidence_ids": STRS, "summary": STR, "expected_impact": NUM},
       ["incident_id", "type", "params", "evidence_ids"])),
    (actions.approve_action, "write", "Approve a proposed action (human in the loop).",
     S({"action_id": STR, "user": STR}, ["action_id"])),
    (actions.reject_action, "write", "Reject a proposed action.", S({"action_id": STR, "user": STR, "reason": STR},
                                                                    ["action_id"])),
    (actions.execute_action, "write", "Execute an approved or auto-approvable action; returns revenue at risk before "
     "and after. Executing twice is a no-op.", S({"action_id": STR}, ["action_id"])),
    (actions.undo_action, "write", "Undo an executed action and restore the before-state.", S({"action_id": STR},
                                                                                              ["action_id"])),
    (actions.draft_notification, "write", "Draft a message to the relationship owner about an action.",
     S({"action_id": STR, "text": STR}, ["action_id"])),
    (memory.get_playbook, "memory", "Best playbook for a disruption type by past success rate.",
     S({"disruption_type": STR}, ["disruption_type"])),
    (memory.recall_similar_episodes, "memory", "Past incidents most similar to this one, with score breakdown.",
     S({"incident_id": STR, "top_k": INT}, ["incident_id"])),
    (memory.record_episode, "memory", "Record the episode for an incident and update its playbook's success rate.",
     S({"incident_id": STR}, ["incident_id"])),
    (memory.upsert_fact, "memory", "Record a temporal fact; a contradiction supersedes the old fact.",
     S({"subject_id": STR, "predicate": STR, "object": STR, "source": STR, "confidence": NUM},
       ["subject_id", "predicate", "object"])),
    (memory.facts_about, "memory", "Facts about an entity (current or with history).",
     S({"subject_id": STR, "include_history": BOOL}, ["subject_id"])),
    (memory.close_incident, "memory", "Close an incident: episode, playbook stats, facts, risk feedback.",
     S({"incident_id": STR}, ["incident_id"])),
    (brain.who_owns, "read", "Current (or as-of date) relationship owner of a supplier (or of a part's/port's "
     "suppliers) with backups.", S({"entity_id": STR, "at": STR}, ["entity_id"])),
    (brain.who_knows, "read", "Employees ranked by documents, messages and decisions about an entity or topic.",
     S({"topic": STR, "entity_id": STR, "k": INT})),
    (brain.trace_decision, "read", "Trace a decision to its source documents and chat messages and the people involved.",
     S({"entity_id": STR, "question": STR, "decision_id": STR})),
    (brain.doc_search, "read", "Vector search over document chunks expanded to documents and mentioned entities.",
     S({"query": STR, "entity_scope": STRS, "k": INT}, ["query"])),
    (brain.changes_since, "read", "Revised documents and decisions since a date.",
     S({"question": STR, "since": STR}, ["question"])),
    (brain.ask, "read", "Answer a company question with sources and the graph path.",
     S({"question": STR, "incident_id": STR}, ["question"])),
]

TOOLS: dict[str, ToolSpec] = {fn.__name__: ToolSpec(fn.__name__, fn, kind, desc, schema) for fn, kind, desc, schema in _DEFS}


def call_tool(scope, name: str, args: dict) -> ToolResult:
    spec = TOOLS.get(name)
    if spec is None:
        raise KeyError(f"unknown tool {name}")
    allowed = set(spec.schema["properties"])
    bad = set(args) - allowed
    if bad:
        from ripple.tools.base import ToolError

        raise ToolError(f"unexpected arguments for {name}: {sorted(bad)}")
    return spec.fn(scope, **args)
