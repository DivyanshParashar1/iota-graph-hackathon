"""Ripple MCP server: every registry tool, tenant-scoped by the server, never by the model.

The tenant comes from (in order) the `CURRENT_TENANT` ContextVar set by an in-process caller, the tenant the
server was built for, or the RIPPLE_TENANT env var (stdio: one server per tenant). Calls with no tenant are
rejected. Tool schemas have no tenant_id argument.

    python -m ripple.mcp_server --tenant dataco          # stdio, for Claude Desktop / any MCP client
"""

from __future__ import annotations

import argparse
import contextvars
import json
import os
from typing import Any

import anyio
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError as MCPToolError
from fastmcp.tools.base import Tool
from fastmcp.tools.base import ToolResult as MCPToolResult

from ripple.config import TENANTS
from ripple.db import DB, TenantScope, get_db
from ripple.ontology import LABELS, RELS
from ripple.tools.base import ToolError, call_context
from ripple.tools.registry import TOOLS, call_tool

CURRENT_TENANT: contextvars.ContextVar[str | None] = contextvars.ContextVar("ripple_tenant", default=None)


class RippleTool(Tool):
    """A registry tool exposed over MCP; resolves the tenant and runs the tool in a worker thread."""

    ripple_name: str = ""
    server_tenant: str | None = None
    db_ref: Any = None

    def _scope(self) -> TenantScope:
        tenant = CURRENT_TENANT.get() or self.server_tenant or os.environ.get("RIPPLE_TENANT")
        if not tenant:
            raise MCPToolError("no tenant bound to this MCP session; refusing to run")
        if tenant not in TENANTS:
            raise MCPToolError(f"unknown tenant {tenant!r}")
        return TenantScope(tenant, self.db_ref or get_db())

    async def run(self, arguments: dict[str, Any]) -> MCPToolResult:
        scope = self._scope()
        if "tenant_id" in arguments or "tenant" in arguments:
            raise MCPToolError("tenant is set by the server, not by tool arguments")

        def work():
            with call_context(agent="mcp"):
                return call_tool(scope, self.ripple_name, dict(arguments))

        try:
            res = await anyio.to_thread.run_sync(work)
        except ToolError as e:
            raise MCPToolError(str(e)) from e
        payload = json.loads(json.dumps(res.to_dict(), default=str))
        payload["tenant"] = scope.tenant_id
        return MCPToolResult(content=json.dumps({"summary": res.summary, "node_ids": res.node_ids[:100]}),
                             structured_content=payload)


def build_server(tenant: str | None = None, db: DB | None = None) -> FastMCP:
    mcp = FastMCP("ripple", instructions="Ripple supply-chain control tower on FalkorDB. Every tool runs Cypher or a "
                                         "graph algorithm over this tenant's ontology and returns node_ids and edges.")
    for name, spec in TOOLS.items():
        mcp.add_tool(RippleTool(name=name, description=spec.description, parameters=spec.schema, ripple_name=name,
                                server_tenant=tenant, db_ref=db, tags={spec.kind}))

    def _scope() -> TenantScope:
        t = CURRENT_TENANT.get() or tenant or os.environ.get("RIPPLE_TENANT")
        if not t:
            raise MCPToolError("no tenant bound to this MCP session")
        return TenantScope(t, db or get_db())

    @mcp.resource("ripple://ontology", mime_type="application/json")
    def ontology() -> str:
        s = _scope()
        counts = {r["l"]: r["c"] for r in s.ops.query("MATCH (n) RETURN labels(n)[0] AS l, count(n) AS c")}
        return json.dumps({"tenant": s.tenant_id, "labels": {k: {"graph": v[0], "description": v[1],
                                                                  "properties": list(v[2]), "count": counts.get(k, 0)}
                                                              for k, v in LABELS.items()},
                           "relationships": [{"type": t, "from": a, "to": b, "properties": p} for t, a, b, p, _ in RELS]})

    @mcp.resource("ripple://incident/{incident_id}", mime_type="application/json")
    def incident(incident_id: str) -> str:
        from ripple.tools.actions import list_actions
        from ripple.tools.impact import get_incident

        s = _scope()
        inc = get_incident(s, incident_id)
        if not inc:
            raise MCPToolError(f"unknown incident {incident_id}")
        return json.dumps({**inc, "actions": list_actions(s, incident_id=incident_id)}, default=str)

    return mcp


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", default=os.environ.get("RIPPLE_TENANT"), choices=list(TENANTS))
    a = ap.parse_args()
    if not a.tenant:
        raise SystemExit("--tenant (or RIPPLE_TENANT) is required")
    build_server(a.tenant).run()  # stdio transport


if __name__ == "__main__":
    main()
