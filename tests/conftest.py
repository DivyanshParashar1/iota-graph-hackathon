"""Shared fixtures.

v2 has no dataset to build, so there is no golden DB: every test that writes gets its own empty embedded
database, which is fast because a tenant starts empty.

**There are no fakes** (plan.md §8). What lives here is a *transport stub*: `StubClient` implements the
provider protocol (`ripple.llm.base.LLMClient`) and returns payloads the test itself wrote, so the route and
store tests can drive the API without a network. It is not an agent: it has no prompt, no logic and no
knowledge of onboarding. Everything that exercises an agent's judgement is a live test under `-m llm`.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

# Tests are offline and deterministic whatever .env holds. `claude_code` would otherwise be picked up from the
# `claude` binary on PATH; live tests re-enable it explicitly.
os.environ.setdefault("RIPPLE_TEST", "1")
os.environ.update(RIPPLE_LLM_PROVIDER="none", OPENROUTER_API_KEY="", ANTHROPIC_API_KEY="")

from ripple.config import get_settings
from ripple.db import TenantScope, close_db, get_db
from ripple.llm.base import Reply, ToolCall, set_client

REMOTE = os.environ.get("RIPPLE_DB_MODE") == "remote"
_next_index = iter(range(1, 10_000))


class StubClient:
    """A transport stub at the provider boundary: it replays payloads the test supplied.

    `script` is a list of either dicts (structured output for a `schema=` call), strings (plain text), or
    `(text, [(tool_name, args), ...])` tuples (a tool-using turn). A callable receives the call kwargs. When
    the script runs out the last entry is repeated, so a test only scripts the turns it cares about.
    """

    name = "stub"
    model = "stub-1"

    def __init__(self, script: list[Any] | None = None):
        self.script = list(script or [{}])
        self.calls: list[dict] = []
        self._n = 0

    def load(self, *script: Any) -> StubClient:
        """Replace the script and forget the calls so far - the script is indexed by call number."""
        self.script = list(script) or [{}]
        self.calls.clear()
        return self

    def complete(self, *, system: str = "", messages: list[dict], tools: list[dict] | None = None,
                 schema: dict | None = None, max_tokens: int | None = None,
                 effort: str | None = None) -> Reply:
        self.calls.append({"system": system, "messages": list(messages), "tools": tools, "schema": schema})
        item = self.script[min(len(self.calls) - 1, len(self.script) - 1)]
        if callable(item):
            item = item({"system": system, "messages": messages, "tools": tools, "schema": schema})
        reply = Reply(model=self.model)
        if isinstance(item, tuple):
            reply.text = item[0]
            for name, args in item[1]:
                self._n += 1
                reply.tool_calls.append(ToolCall(f"stub_{self._n:03d}", name, args))
            reply.stop_reason = "tool_use" if reply.tool_calls else "end_turn"
        elif isinstance(item, dict):
            reply.data = item
            reply.text = item.get("reply") or item.get("text") or ""
        else:
            reply.text = str(item)
        return reply


@pytest.fixture
def stub():
    """A StubClient installed as the process-wide provider for the duration of a test."""
    client = StubClient()
    set_client(client)
    yield client
    set_client(None)


@pytest.fixture(scope="session")
def db(tmp_path_factory):
    """One empty embedded database for the session.

    Tests do not share a tenant: `scope` gives each test its own, and `TenantScope` is the isolation boundary,
    so one server is enough and the suite does not pay ~3s of redis startup per test."""
    if REMOTE:
        d = get_db(mode="remote", db_index=1)
        d.flush()
    else:
        d = get_db(tmp_path_factory.mktemp("db") / "ripple.db", mode="embedded")
    yield d
    close_db(d)


def tenant_id_for(node_name: str) -> str:
    """A valid tenant id derived from the test's name, so a failure names the graph to look in."""
    import re

    base = re.sub(r"[^a-z0-9]+", "_", node_name.lower()).strip("_")[:34]
    return f"t_{base}" if not base or not base[0].isalpha() else base


@pytest.fixture
def scope(db, request):
    """A tenant of this test's own, with its platform indexes applied and its `_Tenant` node in place."""
    from ripple.onboarding.store import create_tenant

    s = TenantScope(tenant_id_for(request.node.name), db)
    s.drop()
    create_tenant(s, "Acme Shoes", "footwear")
    yield s
    s.drop()


@pytest.fixture
def tenants_dir(tmp_path, monkeypatch):
    """Point the per-tenant file mirror at a temporary directory."""
    monkeypatch.setenv("RIPPLE_TENANTS_DIR", str(tmp_path / "tenants"))
    get_settings.cache_clear()
    yield tmp_path / "tenants"
    get_settings.cache_clear()


@pytest.fixture
def app_client(db, stub, request):
    """A TestClient over the app, sharing the session's database and the transport stub.

    The client carries this test's tenant id as a header, so a route test and a store test can run against
    the same server without seeing each other's tenant."""
    from fastapi.testclient import TestClient

    from ripple.api.app import create_app

    tid = tenant_id_for(request.node.name)
    app = create_app(get_settings(), db)
    with TestClient(app, headers={"X-Ripple-Tenant": tid}) as c:
        c.tenant_id = tid
        yield c
    TenantScope(tid, db).drop()
