"""Mitigation planning helpers shared by the scripted Planner, the API and tests.

They call the same tools an LLM planner would (alt_route, alt_suppliers) and turn the results into action params.
"""

from __future__ import annotations

from collections import defaultdict

from ripple.db import TenantScope
from ripple.tools.algos import alt_route
from ripple.tools.base import ToolError, dedupe
from ripple.tools.impact import get_incident, revenue_at_risk
from ripple.tools.sourcing import alt_suppliers

MODE_CODE = {"Standard Class": "STD", "Second Class": "SEC", "First Class": "FST", "Same Day": "SDY"}
SEA = ["Blue Meridian Lines", "Pacific Arc Shipping", "Northstar Freight", "Cobalt Ocean Carriers"]
AIR = ["Atlas Air Cargo", "Skybridge Express"]


def carrier_code(name: str) -> str:
    return "".join(w[0] for w in name.split() if w[0].isalpha()).upper()


def tenant_prefix(scope: TenantScope) -> str:
    return "N-" if scope.tenant_id == "nova" else ""


def port_code(port_id: str) -> str:
    return port_id.split("-")[-1]


def lane_id(scope: TenantScope, origin: str, dest: str, mode: str, carrier: str | None = None) -> str:
    base = f"LANE-{tenant_prefix(scope)}{port_code(origin)}-{port_code(dest)}-{MODE_CODE.get(mode, 'STD')}"
    return f"{base}-{carrier_code(carrier)}" if carrier else base


def plan_reroute(scope: TenantScope, incident_id: str, max_lanes: int = 200) -> dict | None:
    """Group the live impact set by lane and find an alternate lane for each group. Returns REROUTE_ORDERS params
    plus the evidence ids, or None if nothing can be rerouted."""
    inc = get_incident(scope, incident_id)
    if not inc:
        raise ToolError(f"unknown incident {incident_id}")
    dtype = inc["disruption"]["type"]
    targets = [t["id"] for t in inc["targets"]]
    live = revenue_at_risk(scope, incident_id=incident_id).data
    order_ids = live["order_ids"]
    if not order_ids or dtype not in ("port_closure", "carrier_strike"):
        return None
    rows = scope.ops.run("orders_lanes", {"ids": order_ids})
    by_lane: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_lane[r["lane_id"]].append(r)
    lanes = {r["id"]: r for r in scope.ops.run("lanes_get", {"ids": list(by_lane)})}
    groups = sorted(by_lane.items(), key=lambda kv: -sum(o["total"] for o in kv[1]))[:max_lanes]
    route_cache: dict[tuple, dict] = {}
    moves, evidence, routes = [], [], []
    striking = targets and dtype == "carrier_strike" and lanes.get(targets[0], {}).get("carrier")
    for lid, orders in groups:
        ln = lanes[lid]
        if dtype == "port_closure":
            key = (ln["origin"], ln["dest"], ln["mode"])
            if key not in route_cache:
                try:
                    route_cache[key] = alt_route(scope, origin_port=ln["origin"], dest_port=ln["dest"],
                                                 avoid_ports=targets, mode=ln["mode"]).data
                except ToolError:
                    route_cache[key] = None
            rt = route_cache[key]
            if not rt:
                continue
            new_o, new_d = rt["new_origin"], rt["new_dest"]
            to_lane = lane_id(scope, new_o, new_d, ln["mode"])
            transit = rt["lane_transit_days"]
            added = max(0.0, round(transit - float(ln["transit_days"]), 1))
            carrier = ln["carrier"]
            routes.append(rt["route"])
        else:
            strike = striking or ln["carrier"]
            pool = AIR if ln["mode"] == "Same Day" else SEA
            carrier = next(c for c in pool if c != strike)
            new_o, new_d = ln["origin"], ln["dest"]
            to_lane = lane_id(scope, new_o, new_d, ln["mode"], carrier)
            transit = round(float(ln["transit_days"]) + 1.0, 1)
            added = 1.0
        if to_lane == lid:
            continue
        moves.append({"from_lane": lid, "to_lane": to_lane, "to_origin": new_o, "to_dest": new_d, "mode": ln["mode"],
                      "carrier": carrier, "transit_days": transit, "added_days": added,
                      "order_ids": sorted(o["order_id"] for o in orders),
                      "revenue": round(sum(o["total"] for o in orders), 2)})
        evidence.append(lid)
    if not moves:
        return None
    n = sum(len(m["order_ids"]) for m in moves)
    rev = round(sum(m["revenue"] for m in moves), 2)
    top_orders = sorted((o for _, os in groups for o in os), key=lambda o: -o["total"])[:5]
    return {"params": {"moves": moves}, "orders": n, "revenue": rev,
            "max_added_days": max(m["added_days"] for m in moves),
            "evidence": dedupe(targets[:5] + evidence[:10] + [o["order_id"] for o in top_orders] +
                               [p for r in routes[:3] for p in r]),
            "summary": f"Reroute {n} orders on {len(moves)} lanes (max +{max(m['added_days'] for m in moves)} days), "
                       f"${rev:,.0f} protected"}


def plan_alt_suppliers(scope: TenantScope, incident_id: str, parts: list[str]) -> dict | None:
    """For each impacted part, pick the best qualified alternate (outside the failed supplier's country)."""
    inc = get_incident(scope, incident_id)
    countries = dedupe(t.get("country") for t in inc["targets"]) if inc else []
    acts, evidence, details = [], [], []
    for pid in parts:
        r = alt_suppliers(scope, part_id=pid, exclude_country=countries[0] if countries else None).data
        q = [a for a in r["alternates"] if a["relation"] == "QUALIFIED_FOR"]
        if not q:
            continue
        best = q[0]
        acts.append({"part_id": pid, "supplier_id": best["id"], "share": 0.3})
        evidence += [pid, best["id"]]
        details.append(f"{pid}->{best['id']} ({best['country']})")
    if not acts:
        return None
    return {"params": {"activations": acts}, "evidence": dedupe([t["id"] for t in inc["targets"]] + evidence),
            "summary": f"Activate qualified alternates for {len(acts)} part(s): " + ", ".join(details[:4])
                       + ("..." if len(details) > 4 else "")}
