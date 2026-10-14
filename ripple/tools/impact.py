"""Impact tools: event matching, disruptions, incidents, blast radius, revenue at risk, exposure, late risk."""

from __future__ import annotations

from ripple.db import TenantScope, now_ms
from ripple.geo import haversine_km
from ripple.tools.base import ToolError, ToolResult, dedupe, logged_tool, stable_id

HIGHLIGHT_CAP = 200


def _money(x) -> float:
    return round(float(x or 0.0), 2)


@logged_tool
def match_event_to_entities(scope: TenantScope, event: dict) -> ToolResult:
    """Resolve an event {type, target_name | target_id, lat?, lon?, radius_km?} to RiskBearing nodes."""
    g = scope.ops
    etype = event.get("type", "port_closure")
    ents: list[dict] = []
    queries: list[str] = []
    if event.get("target_id"):
        ents = g.run("match_by_id", {"id": event["target_id"]})
        queries.append("match_by_id")
        if not ents and etype == "carrier_strike":
            ents = g.run("match_lanes_by_carrier", {"name": event["target_id"]})
    elif event.get("target_name"):
        name = event["target_name"]
        qn = {"port_closure": "match_port_by_name", "supplier_failure": "match_supplier_by_name",
              "carrier_strike": "match_lanes_by_carrier"}.get(etype, "match_port_by_name")
        ents = g.run(qn, {"name": name})
        queries.append(qn)
    if not ents and event.get("lat") is not None and event.get("lon") is not None:
        r = float(event.get("radius_km", 150))
        rows = g.run("match_near_point", {})
        queries.append("match_near_point")
        for x in rows:
            km = haversine_km(event["lat"], event["lon"], x["lat"], x["lon"])
            if km <= r:
                ents.append({**x, "km": round(km, 1)})
        if etype == "port_closure":
            ents = [e for e in ents if e["label"] == "Port"] or ents
    if not ents:
        raise ToolError(f"no entity matches event {event}")
    countries = dedupe(e.get("country") for e in ents)
    label = ents[0]["label"]
    desc = (f"carrier {event.get('target_name') or event.get('target_id')}: {len(ents)} lanes" if label == "Lane"
            else ", ".join(f"{e['name']} ({e['id']})" for e in ents[:3]))
    return ToolResult({"type": etype, "entities": ents, "countries": countries}, [e["id"] for e in ents], [],
                      queries, summary=f"Matched {desc}")


def disruption_id_for(scope: TenantScope, event: dict, entity_ids: list[str]) -> str:
    """Deterministic: the same event on the same entities is the same disruption (and incident)."""
    return stable_id("DIS", scope.tenant_id, event.get("type"), sorted(entity_ids), event.get("started_at", ""))


@logged_tool
def create_disruption(scope: TenantScope, event: dict, entity_ids: list[str]) -> ToolResult:
    """MERGE a Disruption (deterministic id) that AFFECTS the matched entities."""
    if not entity_ids:
        raise ToolError("create_disruption needs entity_ids")
    did = disruption_id_for(scope, event, entity_ids)
    name = event.get("name") or f"{event.get('type', 'disruption').replace('_', ' ')}: " \
        f"{event.get('target_name') or event.get('target_id')}"
    rows = scope.ops.run("create_disruption", {
        "id": did, "type": event.get("type", "port_closure"), "name": name, "severity": event.get("severity", "high"),
        "started_at": int(event.get("started_at") or now_ms()), "expected_days": int(event.get("expected_days", 7)),
        "source": event.get("source", "api"), "targets": list(entity_ids)})
    n = rows[0]["affects"] if rows else 0
    return ToolResult({"disruption_id": did, "type": event.get("type"), "name": name, "affects": n},
                      [did] + list(entity_ids)[:50], [(did, "AFFECTS", e) for e in list(entity_ids)[:50]],
                      ["create_disruption"], summary=f"Disruption {did} affects {n} node(s)")


def incident_id_for(scope: TenantScope, disruption_id: str) -> str:
    return stable_id("INC", scope.tenant_id, disruption_id)


@logged_tool
def open_incident(scope: TenantScope, disruption_id: str, mode: str = "scripted") -> ToolResult:
    """MERGE the Incident blackboard for a disruption (idempotent)."""
    iid = incident_id_for(scope, disruption_id)
    rows = scope.ops.run("open_incident", {"did": disruption_id, "iid": iid, "ts": now_ms(), "mode": mode})
    if not rows:
        raise ToolError(f"unknown disruption {disruption_id}")
    return ToolResult(rows[0], [iid, disruption_id], [(disruption_id, "TRIGGERED", iid)], ["open_incident"],
                      summary=f"Opened incident {iid}")


def get_incident(scope: TenantScope, incident_id: str) -> dict | None:
    rows = scope.ops.run("incident_get", {"iid": incident_id})
    if not rows or rows[0]["incident"] is None:
        return None
    r = rows[0]
    return {"incident": dict(r["incident"]), "disruption": dict(r["disruption"] or {}),
            "targets": [dict(t) for t in r["targets"] if t.get("id")]}


def _disruption_of(scope: TenantScope, disruption_id: str | None, incident_id: str | None) -> tuple[str, str, str]:
    if incident_id and not disruption_id:
        inc = get_incident(scope, incident_id)
        if not inc:
            raise ToolError(f"unknown incident {incident_id}")
        disruption_id = inc["disruption"]["id"]
    rows = scope.ops.query("MATCH (d:Disruption {id: $id}) RETURN d.type AS type", {"id": disruption_id})
    if not rows:
        raise ToolError(f"unknown disruption {disruption_id}")
    return disruption_id, rows[0]["type"], incident_id or incident_id_for(scope, disruption_id)


def _highlight(scope: TenantScope, dtype: str, did: str, parts: list[str]) -> tuple[list[str], list[tuple]]:
    g = scope.ops
    nodes: list[str] = []
    edges: list[tuple[str, str, str]] = []
    if dtype == "port_closure":
        for r in g.run("blast_paths_port", {"did": did, "limit": 25}):
            nodes += [r["d"], r["port"], r["lane"], r["o"], r["c"]]
            edges += [(r["d"], "AFFECTS", r["port"]), (r["lane"], r["rt"], r["port"]), (r["o"], "SHIPS_VIA", r["lane"]),
                      (r["o"], "PLACED_BY", r["c"])]
            for pr, pl in r["products"][:2]:
                if pr:
                    nodes.append(pr)
                    edges.append((r["o"], "CONTAINS", pr))
                    if pl:
                        nodes.append(pl)
                        edges.append((pr, "MADE_AT", pl))
    elif dtype == "carrier_strike":
        for r in g.run("blast_paths_carrier", {"did": did, "limit": 25}):
            nodes += [r["d"], r["lane"], r["origin"], r["dest"], r["o"], r["c"]]
            edges += [(r["d"], "AFFECTS", r["lane"]), (r["lane"], "ORIGIN", r["origin"]), (r["lane"], "DEST", r["dest"]),
                      (r["o"], "SHIPS_VIA", r["lane"]), (r["o"], "PLACED_BY", r["c"])]
    else:
        prods: list[str] = []
        for r in g.run("blast_paths_supplier", {"did": did, "parts": parts[:30]}):
            ch = r["chain"]
            nodes += [r["d"]] + ch + [r["part"]] + r["products"][:3]
            edges.append((r["d"], "AFFECTS", ch[0]))
            edges += [(a, "SUPPLIES_TO", b) for a, b in zip(ch, ch[1:])]
            edges.append((ch[-1], "SUPPLIES", r["part"]))
            edges += [(r["part"], "COMPONENT_OF", p) for p in r["products"][:3]]
            prods += r["products"][:3]
        for r in g.run("top_orders_for_products", {"products": dedupe(prods)[:20], "limit": 25}):
            nodes += [r["o"], r["c"]]
            edges += [(r["o"], "CONTAINS", r["product"]), (r["o"], "PLACED_BY", r["c"])]
    nodes = dedupe(nodes)[:HIGHLIGHT_CAP]
    keep = set(nodes)
    edges = dedupe(e for e in edges if e[0] in keep and e[2] in keep)
    return nodes, edges


@logged_tool
def blast_radius(scope: TenantScope, disruption_id: str | None = None, incident_id: str | None = None,
                 max_hops: int = 6) -> ToolResult:
    """Orders, revenue, customers, products, parts, suppliers and lanes hit by a disruption, plus a highlight
    subgraph. Writes IMPACTS edges and the numbers onto the Incident blackboard."""
    did, dtype, iid = _disruption_of(scope, disruption_id, incident_id)
    g = scope.ops
    qn = {"port_closure": "blast_radius_port", "supplier_failure": "blast_radius_supplier",
          "carrier_strike": "blast_radius_carrier"}[dtype]
    rows = g.run(qn, {"did": did})
    r = rows[0] if rows else {}
    orders = r.get("orders") or []
    order_ids = sorted(o[0] for o in orders)
    data = {"disruption_id": did, "incident_id": iid, "type": dtype, "orders_at_risk": int(r.get("orders_at_risk") or 0),
            "revenue_at_risk": _money(r.get("revenue_at_risk")), "customers_affected": int(r.get("customers_affected") or 0),
            "lanes": r.get("lanes") or [], "order_ids": order_ids}
    queries = [qn]
    if dtype == "supplier_failure":
        data.update(parts_impacted=r.get("parts") or [], parts_degraded=r.get("degraded") or [],
                    affected_suppliers=r.get("suppliers") or [], product_ids=r.get("products") or [])
    if order_ids:
        ex = g.run("impact_expand", {"order_ids": order_ids})[0]
        data.update(products=ex["products"], parts=ex["parts"], suppliers=ex["suppliers"], plants=ex["plants"])
        data.setdefault("product_ids", ex["product_ids"])
        data["top_mode_market"] = g.run("impact_mode_market", {"order_ids": order_ids})
        queries += ["impact_expand", "impact_mode_market"]
    else:
        data.update(products=0, parts=0, suppliers=0, plants=[], top_mode_market=[])
    nodes, edges = _highlight(scope, dtype, did, data.get("parts_impacted", []))
    queries.append({"port_closure": "blast_paths_port", "carrier_strike": "blast_paths_carrier"}.get(
        dtype, "blast_paths_supplier"))
    summary = (f"{data['orders_at_risk']} open orders, ${data['revenue_at_risk']:,.0f} at risk, "
               f"{data['customers_affected']} customers")
    if g.query("MATCH (i:Incident {id: $iid}) RETURN i.id AS id", {"iid": iid}):
        g.run("write_impacts", {"iid": iid, "rows": [{"id": o, "revenue": _money(t)} for o, t in orders]})
        g.run("set_incident_impact", {"iid": iid, "revenue": data["revenue_at_risk"], "orders": data["orders_at_risk"],
                                      "customers": data["customers_affected"], "summary": summary,
                                      "parts": data.get("parts_impacted", [])})
        queries += ["write_impacts", "set_incident_impact"]
        nodes = [iid] + nodes
    data["highlight"] = {"nodes": nodes, "edges": [list(e) for e in edges]}
    return ToolResult(data, nodes, edges, queries, summary=summary)


@logged_tool
def revenue_at_risk(scope: TenantScope, incident_id: str) -> ToolResult:
    """Live revenue at risk for an incident (recomputed: respects reroutes and supplier switches)."""
    rows = scope.ops.run("revenue_at_risk", {"iid": incident_id})
    r = rows[0] if rows else {"orders": 0, "revenue": 0.0, "order_ids": []}
    rev, n = _money(r["revenue"]), int(r["orders"])
    scope.ops.run("set_incident_live", {"iid": incident_id, "revenue": rev, "orders": n})
    inc = get_incident(scope, incident_id)
    initial = _money((inc or {}).get("incident", {}).get("revenue_at_risk_initial", rev))
    return ToolResult({"incident_id": incident_id, "revenue_at_risk": rev, "orders_at_risk": n,
                       "revenue_at_risk_initial": initial, "order_ids": sorted(r["order_ids"])},
                      [incident_id], [], ["revenue_at_risk", "set_incident_live"],
                      summary=f"${rev:,.0f} at risk across {n} open orders (initially ${initial:,.0f})")


@logged_tool
def customer_exposure(scope: TenantScope, incident_id: str, top_k: int = 10) -> ToolResult:
    """Top customers and customer segments by live revenue at risk."""
    top = scope.ops.run("customer_exposure", {"iid": incident_id, "top_k": int(top_k)})
    segs = scope.ops.run("customer_segments", {"iid": incident_id})
    by_seg: dict[str, dict] = {}
    for s in segs:
        x = by_seg.setdefault(s["segment"], {"segment": s["segment"], "orders": 0, "revenue": 0.0})
        x["orders"] += s["orders"]
        x["revenue"] = _money(x["revenue"] + s["revenue"])
    for t in top:
        t["revenue"] = _money(t["revenue"])
    seg_list = sorted(by_seg.values(), key=lambda x: -x["revenue"])
    lead = seg_list[0] if seg_list else None
    summary = (f"Top customer {top[0]['customer_id']} (${top[0]['revenue']:,.0f}); {lead['segment']} segment "
               f"carries ${lead['revenue']:,.0f}") if top and lead else "No customers exposed"
    edges = [(incident_id, "IMPACTS", t["customer_id"]) for t in top]
    return ToolResult({"top_customers": top, "segments": seg_list, "by_market": segs},
                      [incident_id] + [t["customer_id"] for t in top], edges, ["customer_exposure", "customer_segments"],
                      summary=summary)


@logged_tool
def late_risk_baseline(scope: TenantScope, mode: str, market: str) -> ToolResult:
    """Historical late-delivery rate for a shipping mode and market, from DataCo's Late_delivery_risk labels."""
    r = scope.ops.run("late_risk_baseline", {"mode": mode, "market": market})[0]
    rate = float(r["late_rate"] or 0.0)
    return ToolResult({"mode": mode, "market": market, "late_rate": rate, "sample": int(r["sample"])}, [], [],
                      ["late_risk_baseline"],
                      summary=f"{mode} to {market}: {rate:.0%} historical late rate over {r['sample']} orders")


def trigger(scope: TenantScope, event: dict, mode: str = "scripted") -> tuple[str, str]:
    """match -> create_disruption -> open_incident (the Sentinel's first three steps). Returns (did, iid)."""
    m = match_event_to_entities(scope, event=event)
    d = create_disruption(scope, event=event, entity_ids=m.node_ids)
    i = open_incident(scope, disruption_id=d.data["disruption_id"], mode=mode)
    return d.data["disruption_id"], i.data["id"]
