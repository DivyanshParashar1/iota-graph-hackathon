"""ToolResult, call context and the `logged_tool` decorator shared by every tool.

Tools are plain functions `fn(scope: TenantScope, **args) -> ToolResult`. Agents, the API and tests all call
the same functions. Every call is logged as a `_ToolCall` node in the tenant's ops graph so an expert's answer
can be traced back to the queries behind it.
"""

from __future__ import annotations

import contextvars
import functools
import hashlib
import json
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any

from ripple.db import TenantScope, now_ms


@dataclass
class ToolResult:
    data: Any
    node_ids: list[str] = field(default_factory=list)
    edges: list[tuple[str, str, str]] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    ms: float = 0.0
    summary: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["edges"] = [list(e) for e in self.edges]
        return d


class ToolError(ValueError):
    """Bad arguments or a missing entity; returned to agents as an error tool_result."""


_CTX: contextvars.ContextVar[dict] = contextvars.ContextVar("ripple_call_ctx", default={})


@contextmanager
def call_context(**kw):
    """Set agent / no_log for tool-call logging in this context (thread or task)."""
    tok = _CTX.set({**_CTX.get(), **kw})
    try:
        yield
    finally:
        _CTX.reset(tok)


def current_context() -> dict:
    return dict(_CTX.get())


def stable_id(prefix: str, *parts: Any) -> str:
    h = hashlib.sha1("|".join(json.dumps(p, sort_keys=True, default=str) for p in parts).encode()).hexdigest()
    return f"{prefix}-{h[:10].upper()}"


def dedupe(xs) -> list:
    seen, out = set(), []
    for x in xs:
        if x is not None and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _args_json(kwargs: dict, limit: int = 4000) -> str:
    """Tool arguments as JSON for the _ToolCall node: long values are capped so the text stays valid JSON."""
    from ripple.onboarding.events import slim

    s = json.dumps(slim(kwargs), default=str)
    return s if len(s) <= limit else json.dumps({"truncated": s[:limit]})


def logged_tool(fn):
    """Time the call, fill ToolResult.ms, and write a _ToolCall node (best effort)."""

    @functools.wraps(fn)
    def wrapper(scope: TenantScope, **kwargs) -> ToolResult:
        t0 = time.perf_counter()
        res = fn(scope, **kwargs)
        res.ms = round((time.perf_counter() - t0) * 1000, 2)
        res.node_ids = dedupe(res.node_ids)
        ctx = _CTX.get()
        if not ctx.get("no_log"):
            try:
                scope.ops.run("tool_call_log", {"row": {
                    "id": f"TC-{uuid.uuid4().hex[:12].upper()}", "tool": fn.__name__,
                    "agent": ctx.get("agent", "api"), "args_json": _args_json(kwargs), "ms": res.ms,
                    "ts": now_ms(), "n": len(res.node_ids), "summary": res.summary[:500]}})
            except Exception:  # noqa: BLE001 - logging must never break a tool
                pass
        return res

    wrapper.__ripple_tool__ = True
    return wrapper
