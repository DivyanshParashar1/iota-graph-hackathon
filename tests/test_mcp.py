import json

import pytest
from fastmcp import Client

from ripple.mcp_server import CURRENT_TENANT, build_server
from ripple.tools.registry import TOOLS


async def test_lists_all_tools_without_tenant_args(built_db):
    async with Client(build_server("dataco", built_db)) as c:
        tools = await c.list_tools()
        names = {t.name for t in tools}
        assert names == set(TOOLS)
        for t in tools:
            schema = t.input_schema if hasattr(t, "input_schema") else t.inputSchema
            assert "tenant_id" not in json.dumps(schema) and "tenant" not in schema.get("properties", {})


async def test_call_blast_radius_returns_node_ids(fresh_db):
    async with Client(build_server("dataco", fresh_db)) as c:
        m = await c.call_tool("match_event_to_entities", {"event": {"type": "port_closure", "target_name": "Ningbo"}})
        ids = m.structured_content["node_ids"]
        d = await c.call_tool("create_disruption", {"event": {"type": "port_closure", "target_name": "Ningbo"},
                                                    "entity_ids": ids})
        did = d.structured_content["data"]["disruption_id"]
        await c.call_tool("open_incident", {"disruption_id": did})
        r = await c.call_tool("blast_radius", {"disruption_id": did})
        sc = r.structured_content
        assert sc["tenant"] == "dataco" and sc["node_ids"] and sc["data"]["orders_at_risk"] > 0
        res = await c.read_resource("ripple://ontology")
        onto = json.loads(res[0].text)
        assert onto["labels"]["Order"]["count"] > 0


async def test_call_without_tenant_fails(built_db, monkeypatch):
    monkeypatch.delenv("RIPPLE_TENANT", raising=False)
    async with Client(build_server(None, built_db)) as c:
        with pytest.raises(Exception, match="tenant"):
            await c.call_tool("supplier_influence", {"top_k": 3})


async def test_contextvar_tenant(built_db, monkeypatch):
    monkeypatch.delenv("RIPPLE_TENANT", raising=False)
    tok = CURRENT_TENANT.set("nova")
    try:
        async with Client(build_server(None, built_db)) as c:
            r = await c.call_tool("supplier_influence", {"top_k": 3})
            assert r.structured_content["tenant"] == "nova"
            assert all("-N-" in i for i in r.structured_content["node_ids"])
    finally:
        CURRENT_TENANT.reset(tok)


async def test_tenant_argument_rejected(built_db):
    async with Client(build_server("dataco", built_db)) as c:
        with pytest.raises(Exception):
            await c.call_tool("supplier_influence", {"top_k": 3, "tenant_id": "nova"})
