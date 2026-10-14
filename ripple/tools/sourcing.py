"""Sourcing tools: alternate suppliers for a part and contract terms (with penalty math for an incident)."""

from __future__ import annotations

from ripple.db import TenantScope
from ripple.embed import get_embedder
from ripple.tools.base import ToolError, ToolResult, logged_tool

FM_EVENTS = {"port_closure"}  # disruption types covered by our force majeure clauses (typhoon, port closure)


@logged_tool
def alt_suppliers(scope: TenantScope, part_id: str, exclude_country: str | None = None, limit: int = 5) -> ToolResult:
    """Qualified alternates for a part outside a blocked country, excluding suppliers hit by an active disruption
    (directly or through their upstream tier-2/3)."""
    rows = scope.ops.run("alt_suppliers", {"part": part_id, "exclude_country": exclude_country, "limit": int(limit)})
    if not rows and exclude_country:
        rows = scope.ops.run("alt_suppliers", {"part": part_id, "exclude_country": None, "limit": int(limit)})
    edges = [(r["id"], r["relation"], part_id) for r in rows]
    return ToolResult({"part_id": part_id, "exclude_country": exclude_country, "alternates": rows},
                      [part_id] + [r["id"] for r in rows], edges, ["alt_suppliers"],
                      summary=(f"{len(rows)} alternates for {part_id}; best {rows[0]['name']} ({rows[0]['country']}, "
                               f"reliability {rows[0]['reliability']})") if rows else f"no alternates for {part_id}")


@logged_tool
def contract_terms(scope: TenantScope, supplier_id: str, clause: str = "delay penalty",
                   incident_id: str | None = None) -> ToolResult:
    """The supplier's contract terms and the clause text most relevant to `clause` (vector search scoped to that
    contract). With an incident, also computes the delay penalty we are owed."""
    rows = scope.ops.run("contract_for_supplier", {"sid": supplier_id})
    if not rows:
        raise ToolError(f"no contract with supplier {supplier_id}")
    k = rows[0]
    qvec = get_embedder().embed(clause)
    chunks = scope.ops.run("contract_clause_search", {"doc_id": k["doc_id"], "qvec": qvec, "k": 2})
    queries = ["contract_for_supplier", "contract_clause_search"]
    clause_text = ""
    for c in chunks:
        for para in c["text"].split("\n\n"):
            low = para.lower()
            if any(w in low for w in clause.lower().split() if len(w) > 3) and para[:2].rstrip(".").isdigit():
                clause_text = para
                break
        if clause_text:
            break
    data = {**k, "clause": clause, "clause_text": clause_text or (chunks[0]["text"] if chunks else ""),
            "chunks": chunks}
    nodes = [supplier_id, k["contract_id"], k["doc_id"]] + [c["chunk_id"] for c in chunks]
    summary = (f"{k['supplier']}: {k['penalty_pct']}%/day after {k['sla_days']}-day SLA, cap {k['penalty_cap_pct']}%, "
               f"force majeure {'yes' if k['force_majeure'] else 'no'}")
    if incident_id:
        inc = scope.ops.query("MATCH (d:Disruption)-[:TRIGGERED]->(i:Incident {id: $iid}) RETURN d.type AS type, "
                              "d.expected_days AS days", {"iid": incident_id})
        if inc:
            ex = scope.ops.run("supplier_exposure", {"iid": incident_id, "sid": supplier_id})[0]
            queries.append("supplier_exposure")
            exposure = round(float(ex["revenue"] or 0.0), 2)
            days = int(inc[0]["days"] or 0)
            gross = exposure * k["penalty_pct"] / 100 * days
            capped = min(gross, exposure * k["penalty_cap_pct"] / 100)
            fm = bool(k["force_majeure"]) and inc[0]["type"] in FM_EVENTS
            owed = 0.0 if fm else round(capped, 2)
            data["penalty"] = {"exposed_orders": int(ex["orders"]), "exposed_revenue": exposure, "delay_days": days,
                               "gross": round(gross, 2), "capped": round(capped, 2), "force_majeure_applies": fm,
                               "owed": owed}
            summary += (f"; owed ${owed:,.0f}" + (" (force majeure applies)" if fm else
                                                  f" on ${exposure:,.0f} exposed revenue"))
    return ToolResult(data, nodes, [(k["contract_id"], "WITH", supplier_id), (k["contract_id"], "DOCUMENTED_IN", k["doc_id"])],
                      queries, summary=summary)
