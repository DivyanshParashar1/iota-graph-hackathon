"""Graph-algorithm tools: chokepoints (betweenness + single sourcing), influence (PageRank), clusters (WCC +
label propagation) and alternate routing (weighted k-shortest paths over CONNECTS)."""

from __future__ import annotations

import math
import threading

from ripple.db import TenantScope
from ripple.geo import haversine_km
from ripple.tools.base import ToolError, ToolResult, dedupe, logged_tool

MODE_MULT = {"Standard Class": 1.0, "Second Class": 0.8, "First Class": 0.6, "Same Day": 0.4}
DRAYAGE_KM_PER_DAY = 500.0
MAX_DRAYAGE_KM = 1500.0

_CACHE: dict[tuple, tuple[tuple, list]] = {}
_LOCKS: dict[tuple, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def cached_algo(scope: TenantScope, qname: str, params: dict) -> list[dict]:
    """Run a graph-algorithm query once per supplier-network version (single-flight across threads).

    The supplier network only changes on ingest, while exact betweenness costs seconds; 20 concurrent sessions
    would otherwise queue on FalkorDB's worker threads."""
    key = (id(scope.db), scope.ops.name, qname, tuple(sorted(params.items())))
    ver_row = scope.ops.run("supplier_network_version", {})[0]
    ver = (ver_row["suppliers"], ver_row["edges"])
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(key, threading.Lock())
    with lock:
        hit = _CACHE.get(key)
        if hit and hit[0] == ver:
            return [dict(r) for r in hit[1]]
        rows = scope.ops.run(qname, params)
        _CACHE[key] = (ver, rows)
        return [dict(r) for r in rows]


@logged_tool
def single_points_of_failure(scope: TenantScope, top_k: int = 5, focus_ids: list[str] | None = None) -> ToolResult:
    """Chokepoint suppliers: betweenness centrality on SUPPLIES_TO combined with single-sourced parts downstream."""
    g = scope.ops
    top = cached_algo(scope, "betweenness_suppliers", {"top_k": int(top_k)})
    single = g.run("single_sourced_parts", {"limit": 10000})
    down = {r["id"]: set(r["downstream"]) for r in g.run("supplier_downstream", {"ids": [t["id"] for t in top]})}
    focus = set(focus_ids or [])
    out = []
    for t in top:
        ds = down.get(t["id"], {t["id"]})
        sole = [p for p in single if p["sole_supplier_id"] in ds]
        out.append({**t, "score": round(float(t["score"]), 2), "downstream_tier1": len(ds - {t["id"]}),
                    "single_sourced_parts_downstream": len(sole),
                    "products_exposed": sum(p["products_dependent"] for p in sole),
                    "in_focus": t["id"] in focus})
    flagged = [o for o in out if o["in_focus"]]
    lead = out[0] if out else None
    summary = (f"Top chokepoint {lead['name']} ({lead['id']}, betweenness {lead['score']:.0f}); "
               f"{len(single)} single-sourced parts" if lead else "no suppliers")
    if flagged:
        summary += f"; affected chokepoint: {flagged[0]['id']}"
    return ToolResult({"chokepoints": out, "single_sourced_parts": single[:20], "single_sourced_count": len(single)},
                      [o["id"] for o in out] + [p["part_id"] for p in single[:20]],
                      [(p["sole_supplier_id"], "SUPPLIES", p["part_id"]) for p in single[:20]],
                      ["betweenness_suppliers", "single_sourced_parts", "supplier_downstream"], summary=summary)


@logged_tool
def supplier_influence(scope: TenantScope, top_k: int = 10) -> ToolResult:
    """PageRank over SUPPLIES_TO: the suppliers that the most (important) suppliers depend on."""
    rows = cached_algo(scope, "pagerank_suppliers", {"top_k": int(top_k)})
    for r in rows:
        r["score"] = round(float(r["score"]), 5)
    return ToolResult({"suppliers": rows}, [r["id"] for r in rows], [], ["pagerank_suppliers"],
                      summary=f"Most influential: {rows[0]['name']} ({rows[0]['id']})" if rows else "no suppliers")


@logged_tool
def supplier_clusters(scope: TenantScope, top_k: int = 10) -> ToolResult:
    """Correlated-risk groups: weakly connected components and label-propagation communities of the supplier network."""
    wcc = cached_algo(scope, "wcc_suppliers", {})
    cdlp = cached_algo(scope, "cdlp_suppliers", {})

    def fmt(rows):
        return [{"cluster": r["cluster"], "size": r["size"], "countries": sorted(r["countries"]),
                 "sample_ids": r["ids"][:10]} for r in rows]

    return ToolResult({"components": fmt(wcc)[:top_k], "communities": fmt(cdlp)[:top_k],
                       "n_components": len(wcc), "n_communities": len(cdlp),
                       "covered": sum(r["size"] for r in wcc), "covered_communities": sum(r["size"] for r in cdlp)},
                      [i for r in wcc[:top_k] for i in r["ids"][:3]], [], ["wcc_suppliers", "cdlp_suppliers"],
                      summary=f"{len(wcc)} components (largest {wcc[0]['size']}), {len(cdlp)} communities"
                      if wcc else "no suppliers")


def _sp(scope: TenantScope, a: str, b: str, avoid: list[str]) -> tuple[list[str], float, str] | None:
    rows = scope.ops.run("alt_route", {"from": a, "to": b, "avoid": avoid})
    if rows:
        return rows[0]["route"], float(rows[0]["transit_days"]), "alt_route"
    rows = scope.ops.run("alt_route_unweighted", {"from": a, "to": b, "avoid": avoid})
    if rows:
        return rows[0]["route"], float(rows[0]["transit_days"]), "alt_route_unweighted"
    return None


@logged_tool
def alt_route(scope: TenantScope, origin_port: str, dest_port: str, avoid_ports: list[str] | None = None,
              mode: str = "Standard Class") -> ToolResult:
    """Fastest sea route from origin to destination that avoids the given ports. If the origin (or destination)
    itself is closed, the nearest open port within 1,500 km is used, with trucking (drayage) days added."""
    avoid = list(avoid_ports or [])
    ports = {p["id"]: p for p in scope.ops.run("port_coords", {})}
    if origin_port not in ports or dest_port not in ports:
        raise ToolError(f"unknown port {origin_port} or {dest_port}")

    def candidates(pid: str) -> list[tuple[str, float]]:
        if pid not in avoid:
            return [(pid, 0.0)]
        p = ports[pid]
        near = sorted((haversine_km(p["lat"], p["lon"], q["lat"], q["lon"]), q["id"]) for q in ports.values()
                      if q["id"] not in avoid and q["id"] != pid)
        return [(qid, math.ceil(km / DRAYAGE_KM_PER_DAY)) for km, qid in near if km <= MAX_DRAYAGE_KM][:3]

    mult = MODE_MULT.get(mode, 1.0)
    best = None
    queries = ["port_coords"]
    for o, d_o in candidates(origin_port):
        for d, d_d in candidates(dest_port):
            if o == d:
                continue
            r = _sp(scope, o, d, avoid)
            if not r:
                continue
            route, sea, qn = r
            queries.append(qn)
            total = round(sea * mult + d_o + d_d, 1)
            if best is None or total < best["lane_transit_days"]:
                best = {"route": route, "sea_days": round(sea, 1), "drayage_days": d_o + d_d, "new_origin": o,
                        "new_dest": d, "lane_transit_days": total}
    if best is None:
        raise ToolError(f"no route from {origin_port} to {dest_port} avoiding {avoid}")
    orig = _sp(scope, origin_port, dest_port, []) if origin_port != dest_port else ([origin_port], 0.0, "alt_route")
    orig_days = round(orig[1] * mult, 1) if orig else None
    best.update(origin_port=origin_port, dest_port=dest_port, avoid_ports=avoid, mode=mode,
                original_route=orig[0] if orig else [], original_transit_days=orig_days,
                added_days=round(best["lane_transit_days"] - orig_days, 1) if orig_days is not None else None)
    edges = [(a, "CONNECTS", b) for a, b in zip(best["route"], best["route"][1:])]
    return ToolResult(best, dedupe(best["route"] + [origin_port, dest_port]), edges, dedupe(queries),
                      summary=f"Route {' -> '.join(best['route'])}: {best['lane_transit_days']} days "
                              f"(+{best['added_days']} vs original)")


def warm_caches(scope: TenantScope) -> None:
    """Pre-compute the cached algorithm results and the entity linker (the API calls this at startup)."""
    from ripple.tools.brain import linker

    for qn, params in (("betweenness_suppliers", {"top_k": 5}), ("pagerank_suppliers", {"top_k": 10}),
                       ("wcc_suppliers", {}), ("cdlp_suppliers", {})):
        cached_algo(scope, qn, params)
    linker(scope)
