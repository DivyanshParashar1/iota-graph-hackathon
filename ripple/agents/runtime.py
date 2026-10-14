"""AgentRun: the per-incident runtime every agent (scripted or LLM) uses to call tools, emit events, write
handoffs and remember which node ids it has seen (for the ID validator)."""

from __future__ import annotations

import re
import threading

from ripple.agents.events import BUS, EventBus
from ripple.db import TenantScope, now_ms
from ripple.tools.base import ToolResult, call_context
from ripple.tools.registry import call_tool

ID_RX = re.compile(r"\b[A-Z]{2,5}-[\w-]*\w")


def extract_ids(text: str) -> set[str]:
    return set(ID_RX.findall(text or ""))


class AgentRun:
    def __init__(self, scope: TenantScope, incident_id: str, mode: str = "scripted", bus: EventBus | None = None,
                 llm=None):
        self.scope = scope
        self.incident_id = incident_id
        self.mode = mode
        self.bus = bus or BUS
        self.llm = llm
        self.seen: set[str] = {incident_id}
        self.results: dict[str, list[ToolResult]] = {}
        self._lock = threading.Lock()

    def emit(self, agent: str, kind: str, **kw) -> dict:
        return self.bus.emit(self.incident_id, agent, kind, **kw)

    def remember(self, ids) -> None:
        with self._lock:
            for i in ids:
                if not i:
                    continue
                self.seen.add(i)
                if "#" in i:
                    self.seen.add(i.split("#")[0])

    def call(self, agent: str, tool: str, **args) -> ToolResult:
        self.emit(agent, "tool_call", tool=tool, args=args)
        try:
            with call_context(agent=agent, incident_id=self.incident_id):
                res = call_tool(self.scope, tool, args)
        except Exception as e:
            self.emit(agent, "error", tool=tool, summary=f"{tool} failed: {e}", data={"fatal": False})
            raise
        self.remember(res.node_ids)
        self.remember(e[0] for e in res.edges)
        self.remember(e[2] for e in res.edges)
        with self._lock:
            self.results.setdefault(tool, []).append(res)
        self.emit(agent, "tool_result", tool=tool, summary=res.summary, node_ids=res.node_ids, edges=res.edges,
                  data={**(res.data if isinstance(res.data, dict) else {"result": res.data}), "_ms": res.ms,
                        "_queries": res.queries})
        return res

    def last(self, tool: str) -> ToolResult | None:
        with self._lock:
            r = self.results.get(tool)
            return r[-1] if r else None

    def message(self, agent: str, text: str, node_ids: list | None = None, data=None) -> None:
        self.emit(agent, "message", summary=text, node_ids=node_ids or [], data=data)

    def handoff(self, src: str, dst: str, summary: str) -> None:
        self.scope.ops.run("handoff", {"src": src, "dst": dst, "iid": self.incident_id, "ts": now_ms(),
                                       "summary": summary[:500]})
        self.emit(src, "handoff", summary=f"{src} -> {dst}: {summary}", data={"from": src, "to": dst})
