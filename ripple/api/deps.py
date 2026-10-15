"""Shared API dependencies.

One user = one tenant (plan.md §9.1.3): the tenant id travels in the `ripple_tenant` cookie, which
`POST /api/onboarding/start` sets. A header (`X-Ripple-Tenant`) and a query parameter (`?tenant=`, for
EventSource, which cannot send headers) override it, which is what the tests and the CLI use.

There is no auth. Anyone who can reach the API can name any tenant id in this database - that is the same
trust boundary as the single-user local app the plan assumes, and the open question §9.1.3 is where it changes.
"""

from __future__ import annotations

from fastapi import Cookie, Header, HTTPException, Query, Request

from ripple.db import TenantScope, TenantViolation, valid_tenant_id

COOKIE = "ripple_tenant"


def tenant_id(x_ripple_tenant: str | None = Header(default=None), tenant: str | None = Query(default=None),
              ripple_tenant: str | None = Cookie(default=None)) -> str | None:
    return tenant or x_ripple_tenant or ripple_tenant


def scope_dep(request: Request, tid: str | None = None) -> TenantScope:
    """The current tenant's scope. 404 when there is no tenant yet, 400 on a malformed id."""
    tid = tid or tenant_id(request.headers.get("x-ripple-tenant"),
                           request.query_params.get("tenant"),
                           request.cookies.get(COOKIE))
    if not tid:
        raise HTTPException(404, "no tenant in this session; POST /api/onboarding/start first")
    if not valid_tenant_id(tid):
        raise HTTPException(400, f"bad tenant id {tid!r}")
    db = request.app.state.db
    if f"tenant_{tid}" not in db.list_graphs():
        raise HTTPException(404, f"unknown tenant {tid!r}")
    try:
        return TenantScope(tid, db)
    except TenantViolation as e:
        raise HTTPException(400, str(e)) from None


def tool_error(e: Exception) -> HTTPException:
    return HTTPException(400, str(e))
