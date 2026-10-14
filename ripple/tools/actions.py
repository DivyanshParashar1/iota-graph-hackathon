"""Action tools (Palantir-style action types): propose -> approve/reject -> execute -> undo, plus notifications.

Every Action is a node with a deterministic id (incident, type, params), linked to its incident, the agent
that proposed it, its approver, and BASED_ON evidence nodes. Executing stores the before-state in `undo_json`
so `undo_action` can restore it. Effects are defined so that revenue_at_risk drops (see plan.md section 4).
"""

from __future__ import annotations

import json
import time

from ripple.config import get_settings
from ripple.db import TenantScope, now_ms
from ripple.tools.base import ToolError, ToolResult, current_context, dedupe, logged_tool, stable_id
from ripple.tools.impact import revenue_at_risk

ACTION_TYPES = ("REROUTE_ORDERS", "ACTIVATE_ALT_SUPPLIER", "EXPEDITE", "SPLIT_ORDER", "NOTIFY_OWNER", "PLACE_HOLD")
AUTO_TYPES = ("NOTIFY_OWNER", "PLACE_HOLD")
POLICY_USER = ("USR-policy", "Auto-approval policy")


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M", time.gmtime())


def get_action(scope: TenantScope, action_id: str) -> dict | None:
    rows = scope.ops.run("action_get", {"aid": action_id})
    if not rows or rows[0]["action"] is None:
        return None
    r = rows[0]
    a = dict(r["action"])
    a["params"] = json.loads(a.get("params_json") or "{}")
    a["agent"] = r["agent"]
    a["approved_by"] = r["approved_by"]
    a["evidence"] = [dict(e) for e in r["evidence"] if e.get("id")]
    return a


def list_actions(scope: TenantScope, status: str | None = None, incident_id: str | None = None, limit: int = 100) -> list[dict]:
    rows = scope.ops.run("actions_list", {"status": status, "iid": incident_id, "limit": limit})
    out = []
    for r in rows:
        a = dict(r["action"])
        a["params"] = json.loads(a.get("params_json") or "{}")
        a.pop("params_json", None)
        a.pop("undo_json", None)
        a["agent"] = r["agent"]
        out.append(a)
    return out


def auto_approvable(atype: str, params: dict) -> bool:
    s = get_settings()
    if atype in AUTO_TYPES:
        return True
    if atype == "REROUTE_ORDERS":
        n = sum(len(m.get("order_ids", [])) for m in params.get("moves", []))
        added = max([m.get("added_days", 0) for m in params.get("moves", [])] or [0])
        return n <= s.auto_reroute_max_orders and added <= s.auto_reroute_max_added_days
    return False


def _params_key(params: dict) -> str:
    return json.dumps(params, sort_keys=True, default=str)


@logged_tool
def propose_action(scope: TenantScope, incident_id: str, type: str, params: dict, evidence_ids: list[str],  # noqa: A002
                   agent: str | None = None, summary: str = "", expected_impact: float = 0.0,
                   evidence_roles: dict | None = None) -> ToolResult:
    """Propose an action for an incident with the graph evidence it is BASED_ON. Same inputs -> same action id."""
    if type not in ACTION_TYPES:
        raise ToolError(f"unknown action type {type}; one of {ACTION_TYPES}")
    agent = agent or current_context().get("agent", "planner")
    ev = dedupe(evidence_ids)
    exist = {r["id"]: r for r in scope.ops.run("nodes_exist", {"ids": ev})}
    missing = [x for x in ev if not exist.get(x, {}).get("exists")]
    if missing:
        raise ToolError(f"evidence ids not found in the graph: {missing[:10]}")
    aid = stable_id("ACT", incident_id, type, _params_key(params))
    rows = scope.ops.run("propose_action", {
        "iid": incident_id, "aid": aid, "type": type, "params": _params_key(params), "ts": now_ms(),
        "impact": float(expected_impact or 0.0), "summary": summary, "agent": agent})
    if not rows:
        raise ToolError(f"unknown incident {incident_id}")
    roles = evidence_roles or {}
    scope.ops.run("link_evidence", {"aid": aid, "rows": [{"id": x, "role": roles.get(x, exist[x]["label"].lower())}
                                                          for x in ev]})
    status = rows[0]["status"]
    return ToolResult({"action_id": aid, "type": type, "status": status, "created": rows[0]["created"],
                       "auto_approvable": auto_approvable(type, params), "summary": summary},
                      [aid, incident_id] + ev, [(aid, "FOR_INCIDENT", incident_id)] + [(aid, "BASED_ON", x) for x in ev],
                      ["nodes_exist", "propose_action", "link_evidence"],
                      summary=f"Proposed {type} {aid}" + (f": {summary}" if summary else ""))


@logged_tool
def approve_action(scope: TenantScope, action_id: str, user: str = "USR-demo", user_name: str | None = None) -> ToolResult:
    """Approve a proposed action (human in the loop). Writes Action-[:APPROVED_BY]->User."""
    rows = scope.ops.run("approve_action", {"aid": action_id, "uid": user, "uname": user_name or user, "ts": now_ms()})
    a = get_action(scope, action_id)
    if a is None:
        raise ToolError(f"unknown action {action_id}")
    return ToolResult({"action_id": action_id, "status": a["status"], "changed": bool(rows)}, [action_id, user],
                      [(action_id, "APPROVED_BY", user)], ["approve_action"],
                      summary=f"{action_id} {'approved' if rows else 'unchanged'} ({a['status']})")


@logged_tool
def reject_action(scope: TenantScope, action_id: str, user: str = "USR-demo", reason: str = "",
                  user_name: str | None = None) -> ToolResult:
    """Reject a proposed action. Writes Action-[:REJECTED_BY]->User."""
    rows = scope.ops.run("reject_action", {"aid": action_id, "uid": user, "uname": user_name or user, "ts": now_ms(),
                                           "reason": reason})
    a = get_action(scope, action_id)
    if a is None:
        raise ToolError(f"unknown action {action_id}")
    return ToolResult({"action_id": action_id, "status": a["status"], "changed": bool(rows)}, [action_id, user],
                      [(action_id, "REJECTED_BY", user)], ["reject_action"], summary=f"{action_id} {a['status']}")


# ------------------------------------------------------------------------------------------- effects
def _effect(scope: TenantScope, a: dict) -> tuple[dict, dict, list[str]]:
    """Apply an action's graph effect. Returns (undo_state, result, queries)."""
    g = scope.ops
    p = a["params"]
    aid = a["id"]
    t = a["type"]
    if t == "REROUTE_ORDERS":
        ids = [o for m in p["moves"] for o in m["order_ids"]]
        before = {r["order_id"]: r for r in g.run("orders_lanes", {"ids": ids})}
        moves = []
        undo_rows = []
        for m in p["moves"]:
            keep = [o for o in m["order_ids"] if before.get(o, {}).get("lane_id") == m["from_lane"]]
            undo_rows += [{"order_id": o, "from_lane": m["from_lane"], "to_lane": m["to_lane"],
                           "days_sched": before[o]["days_sched"]} for o in keep]
            moves.append({**m, "order_ids": keep, "added_days": int(round(max(0.0, float(m.get("added_days") or 0))))})
        moved = sum(r["moved"] for r in g.run("exec_reroute", {"aid": aid, "moves": moves}) or [{"moved": 0}])
        return {"rows": undo_rows}, {"moved": moved}, ["orders_lanes", "exec_reroute"]
    if t == "ACTIVATE_ALT_SUPPLIER":
        acts = p.get("activations") or [{"part_id": p["part_id"], "supplier_id": p["supplier_id"], "share": p.get("share", 0.3)}]
        undo_list = []
        for x in acts:
            st = g.run("supplier_part_state", {"pid": x["part_id"], "sid": x["supplier_id"]})[0]
            if st["qualified_on"] is None:
                raise ToolError(f"{x['supplier_id']} is not QUALIFIED_FOR {x['part_id']}")
            g.run("exec_activate_alt_supplier", {"aid": aid, "pid": x["part_id"], "sid": x["supplier_id"],
                                                 "share": float(x.get("share", 0.3))})
            undo_list.append({"pid": x["part_id"], "sid": x["supplier_id"], "qualified_on": st["qualified_on"],
                              "lead_time_days": st["lead_time_days"], "unit_cost": st["unit_cost"],
                              "shares": [dict(s) for s in st["shares"] if s.get("supplier_id")]})
        return {"activations": undo_list}, {"activated": [[x["supplier_id"], x["part_id"]] for x in acts]}, \
            ["supplier_part_state", "exec_activate_alt_supplier"]
    if t == "EXPEDITE":
        before = g.run("orders_lanes", {"ids": p["order_ids"]})
        g.run("exec_expedite", {"ids": p["order_ids"], "cost_per_order": float(p.get("cost_per_order", 120.0)), "aid": aid})
        return {"rows": [{"order_id": r["order_id"], "days_sched": r["days_sched"]} for r in before]}, \
            {"expedited": len(before)}, ["orders_lanes", "exec_expedite"]
    if t == "SPLIT_ORDER":
        before = g.run("orders_lanes", {"ids": [p["order_id"]]})
        if not before:
            raise ToolError(f"unknown order {p['order_id']}")
        child = f"{p['order_id']}-S1"
        g.run("exec_split_order", {"aid": aid, "oid": p["order_id"], "child": child, "to_lane": p["to_lane"],
                                   "fraction": float(p.get("fraction", 0.5))})
        return {"oid": p["order_id"], "child": child, "total": before[0]["total"]}, {"child": child}, \
            ["orders_lanes", "exec_split_order"]
    if t == "PLACE_HOLD":
        before = g.run("orders_lanes", {"ids": p["order_ids"]})
        g.run("exec_place_hold", {"ids": p["order_ids"], "reason": p.get("reason", ""), "aid": aid})
        return {"rows": [{"order_id": r["order_id"], "status": r["status"]} for r in before]}, \
            {"held": len(before)}, ["orders_lanes", "exec_place_hold"]
    if t == "NOTIFY_OWNER":
        mid = f"MSG-{aid}"
        g.run("exec_notify_owner", {"aid": aid, "mid": mid, "eid": p.get("employee_id"), "text": p.get("text", ""),
                                    "ts": _iso_now(), "sent": True})
        return {"mid": mid}, {"message_id": mid, "to": p.get("employee_id")}, ["exec_notify_owner"]
    raise ToolError(f"no effect for {t}")


def _undo_effect(scope: TenantScope, a: dict, undo: dict) -> list[str]:
    g = scope.ops
    t = a["type"]
    if t == "REROUTE_ORDERS":
        g.run("undo_reroute", {"rows": undo["rows"]})
        return ["undo_reroute"]
    if t == "ACTIVATE_ALT_SUPPLIER":
        for u in undo["activations"]:
            g.run("undo_activate_alt_supplier", u)
        return ["undo_activate_alt_supplier"]
    if t == "EXPEDITE":
        g.run("undo_expedite", {"rows": undo["rows"]})
        return ["undo_expedite"]
    if t == "SPLIT_ORDER":
        g.run("undo_split_order", undo)
        return ["undo_split_order"]
    if t == "PLACE_HOLD":
        g.run("undo_place_hold", {"rows": undo["rows"]})
        return ["undo_place_hold"]
    if t == "NOTIFY_OWNER":
        g.run("undo_notify_owner", {"mid": undo["mid"]})
        return ["undo_notify_owner"]
    raise ToolError(f"no undo for {t}")


@logged_tool
def execute_action(scope: TenantScope, action_id: str, agent: str | None = None) -> ToolResult:
    """Apply an approved (or auto-approvable) action to the graph. Executing twice is a no-op. Returns revenue at
    risk before and after."""
    a = get_action(scope, action_id)
    if a is None:
        raise ToolError(f"unknown action {action_id}")
    iid = a.get("incident_id")
    if a["status"] in ("executed", "undone", "rejected", "executing"):
        return ToolResult({"action_id": action_id, "status": a["status"], "noop": True}, [action_id], [], ["action_get"],
                          summary=f"{action_id} already {a['status']}: no-op")
    if a["status"] == "proposed":
        if not auto_approvable(a["type"], a["params"]):
            raise ToolError(f"{action_id} ({a['type']}) needs human approval first")
        scope.ops.run("approve_action", {"aid": action_id, "uid": POLICY_USER[0], "uname": POLICY_USER[1], "ts": now_ms()})
    claim = scope.ops.run("claim_execution", {"aid": action_id})
    if not claim:  # someone else is executing it right now
        return ToolResult({"action_id": action_id, "status": "executing", "noop": True}, [action_id], [], [],
                          summary=f"{action_id} is being executed elsewhere: no-op")
    before = revenue_at_risk(scope, incident_id=iid).data["revenue_at_risk"] if iid else None
    try:
        undo, result, queries = _effect(scope, a)
    except Exception:
        scope.ops.query("MATCH (a:Action {id: $aid}) SET a.status = 'approved'", {"aid": action_id})
        raise
    agent = agent or current_context().get("agent", "api")
    scope.ops.run("finish_execution", {"aid": action_id, "ts": now_ms(), "undo": json.dumps(undo),
                                       "result": json.dumps(result), "agent": agent, "status": "executed"})
    after = revenue_at_risk(scope, incident_id=iid).data["revenue_at_risk"] if iid else None
    delta = f"; revenue at risk ${before:,.0f} -> ${after:,.0f}" if iid else ""
    return ToolResult({"action_id": action_id, "type": a["type"], "status": "executed", "result": result,
                       "revenue_before": before, "revenue_after": after, "noop": False},
                      [action_id] + ([iid] if iid else []), [(agent, "EXECUTED", action_id)],
                      ["action_get", "claim_execution"] + queries + ["finish_execution", "revenue_at_risk"],
                      summary=f"Executed {a['type']} {action_id}{delta}")


@logged_tool
def undo_action(scope: TenantScope, action_id: str) -> ToolResult:
    """Undo an executed action: restore the stored before-state and record a reverse Action (REVERSES)."""
    a = get_action(scope, action_id)
    if a is None:
        raise ToolError(f"unknown action {action_id}")
    if a["status"] != "executed":
        return ToolResult({"action_id": action_id, "status": a["status"], "noop": True}, [action_id], [], [],
                          summary=f"{action_id} is {a['status']}: nothing to undo")
    iid = a.get("incident_id")
    before = revenue_at_risk(scope, incident_id=iid).data["revenue_at_risk"] if iid else None
    queries = _undo_effect(scope, a, json.loads(a.get("undo_json") or "{}"))
    rid = stable_id("ACT", action_id, "undo")
    scope.ops.run("create_reverse_action", {"aid": action_id, "rid": rid, "ts": now_ms(),
                                            "agent": current_context().get("agent", "api")})
    after = revenue_at_risk(scope, incident_id=iid).data["revenue_at_risk"] if iid else None
    return ToolResult({"action_id": action_id, "reverse_action_id": rid, "status": "undone",
                       "revenue_before": before, "revenue_after": after},
                      [action_id, rid], [(rid, "REVERSES", action_id)], queries + ["create_reverse_action"],
                      summary=f"Undid {action_id}" + (f"; revenue at risk ${before:,.0f} -> ${after:,.0f}" if iid else ""))


@logged_tool
def draft_notification(scope: TenantScope, action_id: str, text: str | None = None) -> ToolResult:
    """Draft a message to the relationship owner(s) of the suppliers behind an action, saved as a ChatMessage
    linked to the action (NOTIFIES the owner, ABOUT_ACTION the action)."""
    a = get_action(scope, action_id)
    if a is None:
        raise ToolError(f"unknown action {action_id}")
    p = a["params"]
    sup_ids = dedupe([p.get("supplier_id")] + [x.get("supplier_id") for x in p.get("activations", [])]
                     + [e["id"] for e in a["evidence"] if e["label"] == "Supplier"])
    owners = scope.ops.run("owners_for_entities", {"ids": sup_ids, "now": time.strftime("%Y-%m-%d")}) if sup_ids else []
    eid = p.get("employee_id") or (owners[0]["employee_id"] if owners else None)
    to_name = next((o["name"] for o in owners if o["employee_id"] == eid), None) or p.get("employee_name") or eid
    if text is None:
        inc = scope.ops.query("MATCH (i:Incident {id: $iid}) RETURN i.title AS title, i.revenue_at_risk AS rev, "
                              "i.orders_at_risk AS n", {"iid": a.get("incident_id")})
        i = inc[0] if inc else {"title": a.get("incident_id"), "rev": 0, "n": 0}
        text = (f"Hi {str(to_name).replace(' [SYNTH]', '')}: incident {a.get('incident_id')} ({i['title']}). "
                f"Action {action_id} ({a['type']}, status {a['status']}): {a.get('summary') or ''} "
                f"Currently {i['n'] or 0} open orders / ${float(i['rev'] or 0):,.0f} at risk.")
        if p.get("contract_clause"):
            text += f" Contract: {p['contract_clause']}"
    mid = f"MSG-{action_id}-D"
    scope.ops.run("exec_notify_owner", {"aid": action_id, "mid": mid, "eid": eid, "text": text, "ts": _iso_now(),
                                        "sent": False})
    nodes = [mid, action_id] + ([eid] if eid else []) + sup_ids
    edges = [(mid, "ABOUT_ACTION", action_id)] + ([(mid, "NOTIFIES", eid)] if eid else [])
    return ToolResult({"message_id": mid, "to": eid, "to_name": to_name, "text": text, "owners": owners}, nodes, edges,
                      ["action_get", "owners_for_entities", "exec_notify_owner"],
                      summary=f"Drafted note to {to_name} about {action_id}")
