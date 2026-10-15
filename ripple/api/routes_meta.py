"""Health, tenants, ontology, map."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ripple.agents.orchestrator import effective_mode
from ripple.api.deps import scope_dep
from ripple.config import TENANTS
from ripple.db import TenantScope
from ripple.ontology import INTERFACES, LABELS, RELS

router = APIRouter(prefix="/api")


@router.get("/health")
def health(request: Request):
    db = request.app.state.db
    return {"ok": True, "db_mode": db.mode, "graphs": db.list_graphs(), "agent_mode": effective_mode("llm")[1],
            "default_mode": request.app.state.settings.ripple_agent_mode}


@router.get("/tenants")
def tenants(request: Request):
    out = []
    for t in TENANTS:
        s = TenantScope(t, request.app.state.db)
        c = s.ops.run("tenant_counts", {})
        m = s.mem.run("tenant_counts", {})
        out.append({"id": t, "name": {"dataco": "DataCo Global", "nova": "Nova Retail"}[t],
                    "nodes": c[0]["nodes"] if c else 0, "edges": c[0]["edges"] if c else 0,
                    "memory_nodes": m[0]["nodes"] if m else 0})
    return out


@router.get("/ontology")
def ontology(scope: TenantScope = Depends(scope_dep)):
    st = scope.ops.run("meta_stats", {})[0]
    ms = scope.mem.run("meta_stats", {})[0]
    counts = {**dict(ms["labels"]), **dict(st["labels"])}
    rel_counts = {**dict(ms["relTypes"]), **dict(st["relTypes"])}
    return {"labels": [{"label": k, "graph": v[0], "description": v[1], "properties": v[2], "count": counts.get(k, 0)}
                       for k, v in LABELS.items()],
            "relationships": [{"type": t, "from": a, "to": b, "properties": p, "description": d,
                               "count": rel_counts.get(t, 0)} for t, a, b, p, d in RELS],
            "interfaces": [{"label": k, "on": v[0], "description": v[1]} for k, v in INTERFACES.items()],
            "totals": {"nodes": st["nodeCount"], "edges": st["relCount"], "memory_nodes": ms["nodeCount"]}}


@router.get("/map")
def map_layers(scope: TenantScope = Depends(scope_dep)):
    g = scope.ops
    return {"ports": g.run("map_ports", {}), "plants": g.run("map_plants", {}), "suppliers": g.run("map_suppliers", {}),
            "disruptions": g.run("disruptions_active", {})}
