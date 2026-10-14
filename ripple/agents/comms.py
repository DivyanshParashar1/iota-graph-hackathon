"""Comms / Brain: owners and contracts (prefetch, in parallel with the Analyst), then notifications and the final
incident summary with sources."""

from __future__ import annotations

from ripple.agents.runtime import AgentRun
from ripple.tools.actions import list_actions
from ripple.tools.base import ToolError, dedupe
from ripple.tools.impact import get_incident

NAME = "comms"
TOOLS = ["who_owns", "who_knows", "trace_decision", "doc_search", "contract_terms", "draft_notification"]
ROLE = ("You are Comms. Find who owns the affected supplier relationships, what their contracts say about delays, "
        "draft notifications for the incident's actions and write a short final summary that cites node ids and "
        "document ids from tool results only.")
TOPIC = {"port_closure": "port closure response", "supplier_failure": "supplier failure alternate supplier",
         "carrier_strike": "carrier strike reroute"}


def prefetch_scripted(run: AgentRun) -> str:
    inc = get_incident(run.scope, run.incident_id)
    dtype = inc["disruption"]["type"]
    rel = run.scope.ops.run("related_suppliers", {"iid": run.incident_id, "limit": 3})
    owners, notes = [], []
    for s in rel:
        try:
            r = run.call(NAME, "who_owns", entity_id=s["id"])
        except ToolError:
            continue
        for o in r.data["owners"]:
            if o.get("employee_id"):
                owners.append(o["employee_id"])
                notes.append(f"{o['name'].replace(' [SYNTH]', '')} owns {o['supplier'].replace(' [SYNTH]', '')}")
    k = next((s for s in rel if s["contract_id"]), None)
    clause = ""
    if k:
        c = run.call(NAME, "contract_terms", supplier_id=k["id"], clause="delay penalty")
        clause = c.summary
    wk = run.call(NAME, "who_knows", topic=TOPIC.get(dtype, dtype))
    expert = wk.data["people"][0] if wk.data["people"] else None
    if expert:
        owners.append(expert["employee_id"])
    run.scope.ops.run("set_incident_context", {"iid": run.incident_id, "suppliers": [s["id"] for s in rel],
                                               "owners": dedupe(owners)})
    msg = "; ".join(notes) or "No supplier owners for this disruption"
    if clause:
        msg += f". Contract: {clause}"
    if expert:
        msg += f". Expert: {expert['name'].replace(' [SYNTH]', '')} ({expert['employee_id']})"
    run.message(NAME, msg + ".", [run.incident_id] + dedupe(owners) + [s["id"] for s in rel])
    return msg


def final_scripted(run: AgentRun) -> str:
    inc = get_incident(run.scope, run.incident_id)
    i = inc["incident"]
    acts = [a for a in list_actions(run.scope, incident_id=run.incident_id) if not a["type"].startswith("UNDO_")]
    drafted = []
    for a in acts:
        if a["type"] == "NOTIFY_OWNER":
            continue
        d = run.call(NAME, "draft_notification", action_id=a["id"])
        drafted.append(d.data["message_id"])
    sources = []
    penalty = ""
    rel = i.get("related_suppliers") or []
    for sid in rel:
        try:
            c = run.call(NAME, "contract_terms", supplier_id=sid, clause="delay penalty", incident_id=run.incident_id)
        except ToolError:
            continue
        sources.append(c.data["doc_id"])
        p = c.data.get("penalty")
        if p:
            penalty = (f" Contract {c.data['contract_id']}: " + ("force majeure applies, no penalty owed."
                                                                   if p["force_majeure_applies"] else
                                                                   f"${p['owed']:,.0f} delay penalty owed."))
        break
    live = run.scope.ops.query("MATCH (i:Incident {id: $iid}) RETURN i.revenue_at_risk AS rev, "
                               "i.revenue_at_risk_initial AS rev0, i.orders_at_risk AS n", {"iid": run.incident_id})[0]
    pending = [a for a in acts if a["status"] == "proposed"]
    done = [a for a in acts if a["status"] == "executed"]
    summary = (f"{i.get('title')}: ${float(live['rev0'] or 0):,.0f} was at risk; now ${float(live['rev'] or 0):,.0f} "
               f"across {live['n'] or 0} open orders. {len(done)} action(s) executed, {len(pending)} awaiting approval"
               + (f" ({', '.join(a['id'] for a in pending)})" if pending else "") + "." + penalty)
    run.scope.ops.run("set_incident_summary", {"iid": run.incident_id, "summary": summary, "sources": dedupe(sources)})
    run.message(NAME, summary, [run.incident_id] + [a["id"] for a in acts] + drafted + sources,
                data={"sources": dedupe(sources), "drafts": drafted})
    return summary


def task_prefetch(incident_id: str) -> str:
    return (f"Incident {incident_id}: find the owners of the related suppliers (who_owns) and the delay-penalty "
            f"clause of their contract (contract_terms), and who on the team knows this kind of disruption (who_knows).")


def task_final(incident_id: str) -> str:
    return (f"Incident {incident_id}: draft notifications for its actions (draft_notification) and summarise the "
            f"incident with the penalty owed (contract_terms with incident_id).")
