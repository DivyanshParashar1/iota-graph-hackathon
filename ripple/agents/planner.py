"""Planner: playbook -> mitigation options from graph algorithms -> proposed actions -> auto-execute per policy."""

from __future__ import annotations

from ripple.agents.runtime import AgentRun
from ripple.tools.actions import list_actions
from ripple.tools.base import ToolError, dedupe
from ripple.tools.impact import get_incident

NAME = "planner"
TOOLS = ["get_playbook", "plan_reroute", "plan_alt_suppliers", "alt_route", "alt_suppliers", "contract_terms",
         "propose_action", "execute_action", "revenue_at_risk"]
ROLE = ("You are the Planner. Get the playbook for the incident's disruption type, build mitigation options with "
        "plan_reroute / plan_alt_suppliers (they call alt_route / alt_suppliers), propose them with propose_action "
        "using the returned params and evidence ids, always propose NOTIFY_OWNER for the owner, and execute the "
        "auto-approvable actions. Finish with what you proposed and the revenue at risk now.")


def run_scripted(run: AgentRun) -> str:
    inc = get_incident(run.scope, run.incident_id)
    i, d = inc["incident"], inc["disruption"]
    pb = run.call(NAME, "get_playbook", disruption_type=d["type"]).data["playbook"]
    run.scope.ops.run("set_incident_playbook", {"iid": run.incident_id, "pid": pb["id"], "recalled": None})
    proposed = []
    targets = [t["id"] for t in inc["targets"]]
    for step in pb["steps"]:
        try:
            if step == "REROUTE_ORDERS":
                p = run.call(NAME, "plan_reroute", incident_id=run.incident_id).data["plan"]
                if p:
                    r = run.call(NAME, "propose_action", incident_id=run.incident_id, type="REROUTE_ORDERS",
                                 params=p["params"], evidence_ids=p["evidence"], summary=p["summary"],
                                 expected_impact=p["revenue"])
                    proposed.append(r.data)
            elif step == "ACTIVATE_ALT_SUPPLIER":
                parts = i.get("parts_impacted") or []
                if parts:
                    p = run.call(NAME, "plan_alt_suppliers", incident_id=run.incident_id, part_ids=parts).data["plan"]
                    if p:
                        r = run.call(NAME, "propose_action", incident_id=run.incident_id, type="ACTIVATE_ALT_SUPPLIER",
                                     params=p["params"], evidence_ids=p["evidence"], summary=p["summary"])
                        proposed.append(r.data)
            elif step == "PLACE_HOLD":
                ids = run.call(NAME, "revenue_at_risk", incident_id=run.incident_id).data["order_ids"][:10]
                if ids:
                    r = run.call(NAME, "propose_action", incident_id=run.incident_id, type="PLACE_HOLD",
                                 params={"order_ids": ids, "reason": f"{d['type']} {run.incident_id}"},
                                 evidence_ids=targets[:3] + ids,
                                 summary=f"Hold the {len(ids)} most exposed orders until supply is restored")
                    proposed.append(r.data)
            elif step == "EXPEDITE":
                ids = run.call(NAME, "revenue_at_risk", incident_id=run.incident_id).data["order_ids"][:10]
                if ids:
                    r = run.call(NAME, "propose_action", incident_id=run.incident_id, type="EXPEDITE",
                                 params={"order_ids": ids, "cost_per_order": 120.0}, evidence_ids=targets[:3] + ids,
                                 summary=f"Expedite {len(ids)} orders")
                    proposed.append(r.data)
            elif step == "NOTIFY_OWNER":
                owners = i.get("owner_ids") or []
                eid = owners[0] if owners else None
                if eid:
                    rel = (i.get("related_suppliers") or [])[:1]
                    text = (f"{i.get('title')}: {i.get('orders_at_risk') or 0} open orders / "
                            f"${float(i.get('revenue_at_risk') or 0):,.0f} at risk. Mitigation proposed by Ripple "
                            f"for {run.incident_id}; please review the action queue.")
                    r = run.call(NAME, "propose_action", incident_id=run.incident_id, type="NOTIFY_OWNER",
                                 params={"employee_id": eid, "supplier_id": rel[0] if rel else None, "text": text},
                                 evidence_ids=[eid] + rel + targets[:2], summary=f"Notify {eid}")
                    proposed.append(r.data)
        except ToolError as e:
            run.emit(NAME, "error", summary=f"{step}: {e}", data={"fatal": False})
    executed = []
    for p in proposed:
        if p["auto_approvable"] and p["status"] == "proposed":
            ex = run.call(NAME, "execute_action", action_id=p["action_id"])
            executed.append(p["action_id"])
            run.emit(NAME, "action", summary=ex.summary, node_ids=[p["action_id"]], data=ex.data)
    rv = run.call(NAME, "revenue_at_risk", incident_id=run.incident_id)
    for a in list_actions(run.scope, incident_id=run.incident_id):
        if a["status"] == "proposed":
            run.emit(NAME, "action", summary=f"{a['type']} {a['id']} awaits approval: {a.get('summary', '')}",
                     node_ids=[a["id"]], data={"action_id": a["id"], "status": "proposed", "type": a["type"]})
    msg = (f"Playbook {pb['id']} ({pb['success_rate']:.0%}): proposed {len(proposed)} action(s), auto-executed "
           f"{len(executed)}; ${rv.data['revenue_at_risk']:,.0f} at risk now.")
    run.message(NAME, msg, [run.incident_id, pb["id"]] + dedupe(p["action_id"] for p in proposed))
    return msg


def task(incident_id: str, disruption_type: str) -> str:
    return (f"Plan mitigations for incident {incident_id} (disruption type {disruption_type}). Start with "
            f"get_playbook(disruption_type={disruption_type!r}).")
