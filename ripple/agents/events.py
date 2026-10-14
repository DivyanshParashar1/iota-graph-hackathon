"""In-process pub/sub of agent steps, keyed by incident id. The SSE endpoint replays history then streams.

Thread-safe: agents run in worker threads, SSE consumers in the asyncio loop (they poll; no cross-loop futures).
Event shape (the UI depends on it):
{"seq", "ts", "incident_id", "agent", "kind": tool_call|tool_result|handoff|message|action|done|error,
 "tool", "args", "summary", "node_ids", "edges", "data"}
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import defaultdict
from typing import Any

MAX_LIST = 50
MAX_STR = 2000


def slim(x: Any, depth: int = 0) -> Any:
    """Make tool data small enough for an event: cap lists and strings, drop deep nesting."""
    if depth > 5:
        return "..."
    if isinstance(x, dict):
        return {k: slim(v, depth + 1) for k, v in x.items() if k not in ("embedding",)}
    if isinstance(x, (list, tuple)):
        out = [slim(v, depth + 1) for v in list(x)[:MAX_LIST]]
        if len(x) > MAX_LIST:
            out.append(f"... {len(x) - MAX_LIST} more")
        return out
    if isinstance(x, str) and len(x) > MAX_STR:
        return x[:MAX_STR] + "..."
    if isinstance(x, (int, float, bool)) or x is None or isinstance(x, str):
        return x
    return str(x)


class EventBus:
    def __init__(self):
        self._lock = threading.Lock()
        self._events: dict[str, list[dict]] = defaultdict(list)
        self._done: set[str] = set()

    def emit(self, incident_id: str, agent: str, kind: str, *, tool: str | None = None, args: dict | None = None,
             summary: str = "", node_ids: list | None = None, edges: list | None = None, data: Any = None) -> dict:
        with self._lock:
            ev = {"seq": len(self._events[incident_id]) + 1, "ts": int(time.time() * 1000), "incident_id": incident_id,
                  "agent": agent, "kind": kind, "tool": tool, "args": slim(args or {}), "summary": summary,
                  "node_ids": list(node_ids or [])[:200], "edges": [list(e) for e in (edges or [])][:300],
                  "data": slim(data) if data is not None else None}
            self._events[incident_id].append(ev)
            if kind in ("done", "error"):
                self._done.add(incident_id)
            return ev

    def history(self, incident_id: str, after: int = 0) -> list[dict]:
        with self._lock:
            return list(self._events.get(incident_id, [])[after:])

    def is_done(self, incident_id: str) -> bool:
        with self._lock:
            return incident_id in self._done

    def reset(self, incident_id: str) -> None:
        with self._lock:
            self._events.pop(incident_id, None)
            self._done.discard(incident_id)

    async def stream(self, incident_id: str, after: int = 0, poll: float = 0.1, timeout: float = 300.0):
        seen = after
        t0 = time.time()
        while True:
            new = self.history(incident_id, seen)
            for ev in new:
                seen = ev["seq"]
                yield ev
                if ev["kind"] in ("done", "error"):
                    return
            if (self.is_done(incident_id) and not new) or time.time() - t0 > timeout:
                return
            await asyncio.sleep(poll)


BUS = EventBus()
