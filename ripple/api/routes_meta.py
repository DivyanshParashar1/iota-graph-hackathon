"""Health, config and the current tenant."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ripple.api.deps import COOKIE, scope_dep, scope_for, tenant_id
from ripple.config import get_settings
from ripple.db import TenantScope
from ripple.onboarding import STAGES
from ripple.onboarding.session import progress
from ripple.onboarding.store import counts, get_tenant, instance_counts

router = APIRouter(prefix="/api")


@router.get("/health")
def health(request: Request):
    s = request.app.state.settings
    return {"ok": True, "db_mode": request.app.state.db.mode, "graphs": request.app.state.db.list_graphs(),
            "llm_provider": s.llm_provider, "model": s.model_name, "has_llm": s.has_llm,
            "has_jev": s.has_jev, "jev_model": s.jev_model, "stages": list(STAGES)}


@router.get("/config")
def config():
    s = get_settings()
    return {"llm_provider": s.llm_provider, "configured_provider": s.ripple_llm_provider, "model": s.model_name,
            "effort": s.ripple_llm_effort, "has_llm": s.has_llm, "max_upload_mb": s.ripple_max_upload_mb,
            "stages": list(STAGES)}


@router.get("/tenants")
def tenants(request: Request):
    """Every tenant in this database (one user = one tenant; this is for the demo switcher and the CLI)."""
    out = []
    for tid in request.app.state.db.list_tenants():
        scope = TenantScope(tid, request.app.state.db)
        t = get_tenant(scope) or {"id": tid}
        out.append({**t, **counts(scope)})
    return sorted(out, key=lambda t: t.get("created_at") or 0, reverse=True)


@router.get("/tenant")
def tenant(request: Request):
    """The current tenant and its stage, or 404 when this browser has not started one."""
    tid = tenant_id(request.headers.get("x-ripple-tenant"), request.query_params.get("tenant"),
                    request.cookies.get(COOKIE))
    if not tid or f"tenant_{tid}" not in request.app.state.db.list_graphs():
        raise HTTPException(404, "no tenant in this session")
    scope = TenantScope(tid, request.app.state.db)
    return {**(get_tenant(scope) or {"id": tid}), "counts": instance_counts(scope),
            "progress": progress(scope)}


@router.post("/tenant/select/{tid}")
def select_tenant(tid: str, request: Request, response: Response):
    """Point this browser at an existing tenant (the demo switcher; there is no auth - see api/deps.py)."""
    scope = scope_for(request, tid)
    response.set_cookie(COOKIE, scope.tenant_id, max_age=60 * 60 * 24 * 365, samesite="lax")
    return {**(get_tenant(scope) or {"id": tid})}


@router.get("/graph")
def graph_sample(limit: int = 300, scope: TenantScope = Depends(scope_dep)):
    """A sample of the instance graph for the graph view: nodes with their titles, and the edges between them."""
    n = max(1, min(limit, 2000))
    nodes = scope.ops.run("graph_nodes_sample", {"limit": n})
    edges = scope.ops.run("graph_edges_between",
                          {"ids": sorted({x["id"] for x in nodes}), "limit": min(n * 4, 8000)})
    return {"nodes": nodes, "edges": edges}
