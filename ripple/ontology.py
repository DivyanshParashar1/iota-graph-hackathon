"""Single source of truth for the Ripple ontology (object types, link types, interfaces).

`python -m ripple.ontology` regenerates graph/ontology.md. The API's /api/ontology and the LLM agents'
system prompts read from here too.
"""

from __future__ import annotations

from ripple import ROOT

# label -> (graph, description, {property: description})
LABELS: dict[str, tuple[str, str, dict[str, str]]] = {
    "Supplier": ("ops", "A company that supplies parts (tier 1) or supplies other suppliers (tier 2/3). Synthetic.", {
        "id": "SUP-T<tier>-NNNN", "name": "company name tagged [SYNTH]", "tier": "1, 2 or 3", "country": "ISO-2",
        "lat": "latitude", "lon": "longitude", "capacity": "units/month", "reliability": "0.6-0.99",
        "risk_score": "0-1", "synthetic": "always true"}),
    "Part": ("ops", "A component in a product's bill of materials.", {
        "id": "PRT-NNNN", "name": "part name", "category": "part family", "department": "DataCo department",
        "unit_cost": "USD", "criticality": "low|medium|high"}),
    "Product": ("ops", "A DataCo product (real).", {
        "id": "PRD-<Product Card Id>", "name": "product name", "category": "DataCo category",
        "department": "DataCo department", "price": "USD"}),
    "Plant": ("ops", "A manufacturing plant (synthetic) where products are made.", {
        "id": "PLT-NN", "name": "plant name", "country": "ISO-2", "lat": "", "lon": ""}),
    "Port": ("ops", "A real seaport (public name and coordinates). RiskBearing.", {
        "id": "PORT-<UN/LOCODE>", "name": "port name", "country": "ISO-2", "lat": "", "lon": "",
        "status": "open|disrupted", "risk_score": "0-1"}),
    "Lane": ("ops", "A shipping lane from an origin port to a destination port with a mode and carrier. RiskBearing.", {
        "id": "LANE-<orig>-<dest>-<mode>", "mode": "DataCo Shipping Mode", "transit_days": "days",
        "carrier": "synthetic carrier", "risk_score": "0-1"}),
    "Order": ("ops", "A DataCo order (real). Grouped from order items.", {
        "id": "ORD-<Order Id>", "date": "ISO datetime", "status": "DataCo Order Status", "open": "status is open",
        "region": "Order Region", "market": "Market", "country": "Order Country", "city": "Order City",
        "total": "sum(Sales) of its lines, USD", "profit": "sum of Order Profit Per Order",
        "late_risk": "Late_delivery_risk (0/1)", "delivery_status": "", "days_real": "", "days_sched": "",
        "shipping_mode": "Shipping Mode"}),
    "OrderLine": ("ops", "One DataCo order item.", {"id": "OL-<Order Item Id>", "qty": "", "total": "Sales", "price": ""}),
    "Customer": ("ops", "A DataCo customer. No names, emails or streets are loaded.", {
        "id": "CUS-<Customer Id>", "segment": "", "city": "", "state": "", "country": ""}),
    "Market": ("ops", "DataCo market.", {"id": "MKT-<name>", "name": ""}),
    "Region": ("ops", "DataCo order region.", {"id": "REG-<slug>", "name": ""}),
    "Disruption": ("ops", "An event that affects RiskBearing nodes.", {
        "id": "DIS-<hash>", "type": "port_closure|supplier_failure|carrier_strike", "name": "", "severity": "",
        "started_at": "epoch ms", "expected_days": "", "source": "scenario|api|gdacs", "active": "bool"}),
    "Incident": ("ops", "The shared blackboard that agents read and write.", {
        "id": "INC-<hash>", "status": "open|closed", "type": "disruption type", "title": "",
        "opened_at": "epoch ms", "closed_at": "", "revenue_at_risk": "live USD", "revenue_at_risk_initial": "USD",
        "orders_at_risk": "", "customers_affected": "", "summary": "", "mode": "scripted|llm"}),
    "Action": ("ops", "A proposed or executed mitigation (Palantir-style action type).", {
        "id": "ACT-<hash>", "type": "REROUTE_ORDERS|ACTIVATE_ALT_SUPPLIER|EXPEDITE|SPLIT_ORDER|NOTIFY_OWNER|PLACE_HOLD",
        "status": "proposed|approved|executed|rejected|undone", "params_json": "JSON", "created_at": "",
        "executed_at": "", "expected_impact": "USD", "undo_json": "before-state JSON", "summary": ""}),
    "Agent": ("ops", "One of the four agents.", {"id": "AGT-<name>", "name": "sentinel|analyst|planner|comms"}),
    "ToolCall": ("ops", "One logged tool call (traceability).", {
        "id": "TC-<uuid>", "tool": "", "agent": "", "args_json": "", "ms": "", "ts": "", "n_nodes": ""}),
    "User": ("ops+mem", "A human approver / chat user.", {"id": "USR-<name>", "name": ""}),
    "Employee": ("ops", "A synthetic employee.", {
        "id": "EMP-NNN", "name": "[SYNTH]", "role": "", "contact": "work email, @ripple-demo.example"}),
    "Team": ("ops", "A team.", {"id": "TEAM-<code>", "name": ""}),
    "Contract": ("ops", "A supply contract with a tier-1 supplier.", {
        "id": "CON-NNNN", "supplier_id": "", "start": "", "end": "", "sla_days": "", "penalty_pct": "per day late",
        "penalty_cap_pct": "", "force_majeure": "bool", "exclusivity": "bool", "doc_id": ""}),
    "Document": ("ops", "A contract, SOP, postmortem or chat thread.", {
        "id": "DOC-...", "type": "contract|sop|postmortem|chat_thread", "title": "", "uri": "repo path",
        "version": "", "updated_at": "ISO date"}),
    "Chunk": ("ops", "A paragraph-sized piece of a document with an embedding.", {
        "id": "<doc id>#<n>", "text": "", "ordinal": "", "embedding": "vecf32(384)"}),
    "Thread": ("ops", "A chat thread.", {"id": "THR-...", "channel": "", "title": ""}),
    "ChatMessage": ("ops", "A company chat message (Slack-style).", {
        "id": "MSG-...", "ts": "ISO datetime", "text": "", "embedding": "vecf32(384)"}),
    "Decision": ("ops", "A decision recorded in a postmortem or chat.", {
        "id": "DEC-...", "summary": "", "decided_at": "ISO date", "status": "active|superseded"}),
    "Episode": ("mem", "Episodic memory: one closed incident.", {
        "id": "EPI-...", "incident_id": "", "disruption_type": "", "entity_ids": "list", "countries": "list",
        "actions_taken": "list", "outcome": "resolved|partial|failed", "revenue_before": "", "revenue_after": "",
        "summary": "", "embedding": "vecf32(384)", "ts": ""}),
    "Playbook": ("mem", "Procedural memory: ordered action types with a success rate.", {
        "id": "PB-...", "disruption_type": "", "name": "", "steps": "list of action types", "uses": "",
        "successes": "", "success_rate": ""}),
    "Fact": ("mem", "Semantic memory: a temporal fact.", {
        "id": "FACT-...", "subject_id": "ops node id", "predicate": "", "object": "", "valid_at": "epoch ms",
        "invalid_at": "epoch ms or null (current)", "source": "", "confidence": ""}),
    "Conversation": ("mem", "A chat with Ripple.", {"id": "CONV-...", "user_id": "", "started_at": ""}),
    "ConvMessage": ("mem", "One turn of a chat with Ripple.", {
        "id": "CMSG-...", "role": "user|assistant", "text": "", "ts": "", "sources_json": ""}),
}

INTERFACES = {"RiskBearing": ("Supplier, Port, Lane", "Anything a Disruption can AFFECT; carries risk_score")}

# (type, from, to, properties, description)
RELS: list[tuple[str, str, str, str, str]] = [
    ("SUPPLIES", "Supplier", "Part", "lead_time_days, unit_cost, share", "Active supply (tier 1)"),
    ("QUALIFIED_FOR", "Supplier", "Part", "qualified_on", "Qualified alternate, not active"),
    ("SUPPLIES_TO", "Supplier", "Supplier", "", "Tier linkage: tier3 -> tier2 -> tier1"),
    ("SHIPS_FROM", "Supplier", "Port", "", "Supplier's export port"),
    ("COMPONENT_OF", "Part", "Product", "qty", "Bill of materials"),
    ("MADE_AT", "Product", "Plant", "", "Where a product is made"),
    ("NEAR", "Plant", "Port", "km", "Plant's export port"),
    ("CONTAINS", "Order", "OrderLine", "", "Order items"),
    ("CONTAINS", "OrderLine", "Product", "", "Item's product"),
    ("PLACED_BY", "Order", "Customer", "", ""),
    ("SHIPS_VIA", "Order", "Lane", "", "Current lane (re-pointed by REROUTE_ORDERS)"),
    ("ORIGIN", "Lane", "Port", "", ""),
    ("DEST", "Lane", "Port", "", ""),
    ("CONNECTS", "Port", "Port", "transit_days", "Materialized from lanes for routing"),
    ("IN_MARKET", "Order", "Market", "", ""),
    ("IN_REGION", "Order", "Region", "", ""),
    ("PART_OF", "Region", "Market", "", ""),
    ("AFFECTS", "Disruption", "RiskBearing", "severity", ""),
    ("TRIGGERED", "Disruption", "Incident", "", ""),
    ("IMPACTS", "Incident", "Order", "revenue", "Top impacted orders"),
    ("HAS_CALL", "Incident", "ToolCall", "", "Tool trace"),
    ("PROPOSED", "Agent", "Action", "ts", ""),
    ("EXECUTED", "Agent", "Action", "ts", ""),
    ("BASED_ON", "Action", "any", "role", "Evidence"),
    ("FOR_INCIDENT", "Action", "Incident", "", ""),
    ("APPROVED_BY", "Action", "User", "ts", "Governance"),
    ("REJECTED_BY", "Action", "User", "ts", ""),
    ("REVERSES", "Action", "Action", "", "Undo"),
    ("NOTIFIES", "ChatMessage", "Employee", "", "Drafted notification"),
    ("ABOUT_ACTION", "ChatMessage", "Action", "", ""),
    ("HANDED_OFF_TO", "Agent", "Agent", "incident_id, ts, summary", "Handoff between agent steps"),
    ("OWNS_RELATIONSHIP", "Employee", "Supplier", "valid_from, valid_to", "Temporal ownership"),
    ("MEMBER_OF", "Employee", "Team", "", ""),
    ("WITH", "Contract", "Supplier", "", ""),
    ("DOCUMENTED_IN", "Contract", "Document", "", ""),
    ("HAS_CHUNK", "Document", "Chunk", "", ""),
    ("MENTIONS", "Chunk|ChatMessage", "any", "confidence", "Entity linking"),
    ("AUTHORED", "Employee", "Document", "", ""),
    ("POSTED", "Employee", "ChatMessage", "", ""),
    ("HAS_MSG", "Thread", "ChatMessage", "", ""),
    ("THREAD_DOC", "Thread", "Document", "", "The thread's citable document"),
    ("SOURCED_FROM", "Decision", "Document|ChatMessage", "", "Where a decision was made"),
    ("ABOUT", "Decision", "Supplier|Part|Port", "", ""),
    ("PARTICIPATED_IN", "Employee", "Decision", "", ""),
    ("USED", "Episode", "Playbook", "", "mem graph"),
    ("SUPERSEDES", "Fact", "Fact", "", "mem graph: newer fact supersedes older"),
    ("HAD", "User", "Conversation", "", "mem graph"),
    ("HAS_MSG", "Conversation", "ConvMessage", "", "mem graph"),
]


def summary_text() -> str:
    """Compact ontology summary for LLM system prompts."""
    labels = "; ".join(f"{k}({', '.join(v[2])})" for k, v in LABELS.items())
    rels = "; ".join(f"({a})-[:{t}]->({b})" for t, a, b, _, _ in RELS)
    return f"Labels: {labels}\nRelationships: {rels}"


def to_markdown() -> str:
    out = ["# Ripple ontology", "", "Generated by `python -m ripple.ontology` from `ripple/ontology.py`. Do not edit.", "",
           "Graphs: `tenant_<id>` (ops: operational data + company brain + incidents/actions) and `mem_<id>` "
           "(agent memory). Cross-graph references are id strings.", "", "## Object types (node labels)", "",
           "| Label | Graph | Description | Properties |", "|---|---|---|---|"]
    for k, (g, d, props) in LABELS.items():
        ps = ", ".join(f"`{p}`" + (f" ({v})" if v else "") for p, v in props.items())
        out.append(f"| `{k}` | {g} | {d} | {ps} |")
    out += ["", "## Interfaces", "", "| Label | On | Meaning |", "|---|---|---|"]
    for k, (on, d) in INTERFACES.items():
        out.append(f"| `{k}` | {on} | {d} |")
    out += ["", "## Link types (relationships)", "", "| Type | From → To | Properties | Description |", "|---|---|---|---|"]
    for t, a, b, p, d in RELS:
        out.append(f"| `{t}` | {a} → {b} | {p} | {d} |")
    out += ["", "## Diagram", "", "```mermaid", "graph LR"]
    seen = set()
    for t, a, b, _, _ in RELS:
        for x in a.split("|"):
            for y in b.split("|"):
                if y == "any" or (x, t, y) in seen:
                    continue
                seen.add((x, t, y))
                out.append(f"  {x} -- {t} --> {y}")
    out += ["```", ""]
    return "\n".join(out)


def write_markdown() -> None:
    (ROOT / "graph" / "ontology.md").write_text(to_markdown())


if __name__ == "__main__":
    write_markdown()
    print("wrote graph/ontology.md")
