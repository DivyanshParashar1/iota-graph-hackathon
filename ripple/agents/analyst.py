"""Impact Analyst: blast radius, live revenue at risk, customer exposure, late-risk baseline, chokepoints."""

from __future__ import annotations

from ripple.agents.runtime import AgentRun
from ripple.tools.impact import get_incident

NAME = "analyst"
TOOLS = ["blast_radius", "revenue_at_risk", "customer_exposure", "late_risk_baseline", "single_points_of_failure",
         "supplier_influence", "supplier_clusters"]
ROLE = ("You are the Impact Analyst. Compute the blast radius of the incident's disruption, the live revenue at risk, "
        "the most exposed customers, the historical late rate for the most affected shipping mode and market, and "
        "whether a chokepoint supplier is involved. Finish with a 2-3 sentence impact summary with numbers.")


def run_scripted(run: AgentRun) -> str:
    inc = get_incident(run.scope, run.incident_id)
    did = inc["disruption"]["id"]
    br = run.call(NAME, "blast_radius", disruption_id=did)
    rv = run.call(NAME, "revenue_at_risk", incident_id=run.incident_id)
    ce = run.call(NAME, "customer_exposure", incident_id=run.incident_id, top_k=5)
    lr = None
    tmm = br.data.get("top_mode_market") or []
    if tmm:
        lr = run.call(NAME, "late_risk_baseline", mode=tmm[0]["mode"], market=tmm[0]["market"])
    focus = [t["id"] for t in inc["targets"] if t["label"] == "Supplier"]
    sp = run.call(NAME, "single_points_of_failure", top_k=5, focus_ids=focus)
    hops = {"port_closure": "Disruption->Port<-Lane<-Order->OrderLine->Product<-Part<-Supplier",
            "supplier_failure": "Disruption->Supplier-SUPPLIES_TO*->Supplier->Part->Product<-OrderLine<-Order->Customer",
            "carrier_strike": "Disruption->Lane<-Order->Customer"}.get(br.data["type"], "")
    msg = (f"{br.data['orders_at_risk']} open orders, ${rv.data['revenue_at_risk']:,.0f} at risk, "
           f"{br.data['customers_affected']} customers, {br.data.get('products', 0)} products, "
           f"{br.data.get('parts', 0)} parts, {br.data.get('suppliers', 0)} suppliers ({hops}).")
    if lr:
        msg += f" Baseline late rate for {lr.data['mode']} to {lr.data['market']}: {lr.data['late_rate']:.0%}."
    if ce.data["top_customers"]:
        msg += f" {ce.summary}."
    flagged = [c for c in sp.data["chokepoints"] if c["in_focus"]]
    if flagged:
        msg += (f" The failed supplier {flagged[0]['id']} is a chokepoint (betweenness {flagged[0]['score']:.0f}, "
                f"{flagged[0]['downstream_tier1']} tier-1 customers).")
    run.message(NAME, msg, [run.incident_id] + br.node_ids[:50])
    return msg


def task(incident_id: str) -> str:
    return f"Analyse incident {incident_id}: start with blast_radius(incident_id={incident_id!r})."
