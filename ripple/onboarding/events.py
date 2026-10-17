"""In-process pub/sub of agent steps, keyed by tenant. `GET /api/onboarding/stream` replays history then streams.

Thread-safe: agents run in worker threads, SSE consumers in the asyncio loop (they poll; no cross-loop futures).
The stream is a live view of what the agents are doing, not the source of truth - every step is also written to
FalkorDB by `store.record_step`, so a reconnecting browser can rebuild the trail from the graph.

Event shape (the UI depends on it):
{"seq", "ts", "tenant", "stage", "agent", "kind": llm|tool|write|stage|message|form|error|done, "summary",
 "node_ids", "data"}
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import defaultdict
from typing import Any

MAX_LIST = 50
MAX_STR = 2000
MAX_HISTORY = 2000


def slim(x: Any, depth: int = 0) -> Any:
    """Make agent data small enough for an event: cap lists and strings, drop deep nesting."""
    if depth > 6:
        return "..."
    if isinstance(x, dict):
        return {k: slim(v, depth + 1) for k, v in x.items() if k not in ("embedding", "system_prompt")}
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
    """One bounded ring of events per tenant, plus a turn counter so the UI can show "agent is working"."""

    def __init__(self):
        self._lock = threading.Lock()
        self._events: dict[str, list[dict]] = defaultdict(list)
        self._seq: dict[str, int] = defaultdict(int)
        self._busy: dict[str, int] = defaultdict(int)

    def emit(self, tenant: str, agent: str, kind: str, *, stage: str = "", summary: str = "",
             node_ids: list | None = None, data: Any = None) -> dict:
        with self._lock:
            self._seq[tenant] += 1
            ev = {"seq": self._seq[tenant], "ts": int(time.time() * 1000), "tenant": tenant, "stage": stage,
                  "agent": agent, "kind": kind, "summary": summary,
                  "node_ids": list(node_ids or [])[:200], "data": slim(data) if data is not None else None}
            buf = self._events[tenant]
            buf.append(ev)
            if len(buf) > MAX_HISTORY:
                del buf[:-MAX_HISTORY]
            return ev

    def seed(self, tenant: str, steps: list[dict]) -> None:
        """Rebuild a tenant's history from its persisted steps (`store.list_steps`) after a restart emptied the
        ring. A no-op once the tenant has any event, so a live turn is never replayed twice."""
        with self._lock:
            if self._events.get(tenant):
                return
            buf = self._events[tenant]
            for s in steps[-MAX_HISTORY:]:
                self._seq[tenant] += 1
                buf.append({"seq": self._seq[tenant], "ts": s.get("ts") or 0, "tenant": tenant,
                            "stage": s.get("stage") or "", "agent": s.get("agent") or "", "kind": s.get("kind"),
                            "summary": s.get("summary") or "", "node_ids": [], "data": s.get("payload") or None})

    def history(self, tenant: str, after: int = 0) -> list[dict]:
        with self._lock:
            return [e for e in self._events.get(tenant, []) if e["seq"] > after]

    def busy(self, tenant: str) -> bool:
        with self._lock:
            return self._busy[tenant] > 0

    def enter(self, tenant: str) -> None:
        with self._lock:
            self._busy[tenant] += 1

    def try_enter(self, tenant: str) -> bool:
        """Enter only when no turn is running for this tenant: one agent turn at a time."""
        with self._lock:
            if self._busy[tenant] > 0:
                return False
            self._busy[tenant] += 1
            return True

    def leave(self, tenant: str) -> None:
        with self._lock:
            self._busy[tenant] = max(0, self._busy[tenant] - 1)

    def reset(self, tenant: str) -> None:
        with self._lock:
            self._events.pop(tenant, None)
            self._seq.pop(tenant, None)
            self._busy.pop(tenant, None)

    async def stream(self, tenant: str, after: int = 0, poll: float = 0.15, timeout: float = 3600.0):
        """Replay everything after `after`, then stream new events until the client disconnects."""
        seen = after
        t0 = time.time()
        while time.time() - t0 < timeout:
            for ev in self.history(tenant, seen):
                seen = ev["seq"]
                yield ev
            await asyncio.sleep(poll)


BUS = EventBus()


class StepEmitter:
    """Emits to the bus and records to the graph in one call, so the live stream and the audit trail agree."""

    def __init__(self, scope, stage: str, agent: str):
        self.scope = scope
        self.stage = stage
        self.agent = agent

    def __call__(self, kind: str, summary: str = "", *, data: Any = None, node_ids: list | None = None,
                 ms: float = 0.0) -> dict:
        from ripple.onboarding.models import AgentStep
        from ripple.onboarding.store import record_step

        ev = BUS.emit(self.scope.tenant_id, self.agent, kind, stage=self.stage, summary=summary,
                      node_ids=node_ids, data=data)
        try:
            record_step(self.scope, AgentStep(stage=self.stage, agent=self.agent, kind=kind, summary=summary,
                                              payload=slim(data) if isinstance(data, dict) else {}, ms=ms))
        except Exception:  # noqa: BLE001 - the audit write must never break a turn
            pass
        return ev
