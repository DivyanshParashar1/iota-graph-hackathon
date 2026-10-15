"""Shared API dependencies: the tenant scope from the X-Ripple-Tenant header, or a `tenant` query parameter for
EventSource (which cannot send headers). Unknown tenant -> 404."""

from __future__ import annotations

from fastapi import Header, HTTPException, Query, Request

from ripple.config import TENANTS
from ripple.db import TenantScope


def scope_dep(request: Request, x_ripple_tenant: str = Header(default="dataco"),
              tenant: str | None = Query(default=None)) -> TenantScope:
    t = tenant or x_ripple_tenant
    if t not in TENANTS:
        raise HTTPException(404, f"unknown tenant {t!r}")
    return TenantScope(t, request.app.state.db)


def tool_error(e: Exception) -> HTTPException:
    return HTTPException(400, str(e))
