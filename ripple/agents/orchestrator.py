"""LangGraph orchestration: sentinel -> (analyst || comms_prefetch) -> planner -> comms -> END.

State holds only ids; agents read and write the Incident blackboard in FalkorDB and record
(:Agent)-[:HANDED_OFF_TO {incident_id, ts, summary}]->(:Agent). Each node runs scripted logic or the LLM loop
(with scripted fallbacks that are safe to re-run because every write is an idempotent MERGE).
"""

from __future__ import annotations

import threading
import time

from langgraph.graph import END, START, StateGraph

from ripple.agents import analyst, comms, planner, sentinel
from ripple.agents.events import BUS, EventBus
from ripple.agents.llm import get_client, run_llm_agent
from ripple.agents.runtime import AgentRun
from ripple.agents.state import IncidentState
from ripple.db import TenantScope
from ripple.tools.base import call_context
from ripple.tools.impact import disruption_id_for, get_incident, incident_id_for, match_event_to_entities


def prepare(scope: TenantScope, event: dict) -> tuple[str, str]:
    """Resolve the deterministic disruption and incident ids for an event (no side effects)."""
    with call_context(no_log=True):
        m = match_event_to_entities(scope, event=event)
    did = disruption_id_for(scope, event, m.node_ids)
    return did, incident_id_for(scope, did)


def effective_mode(mode: str, client=None) -> tuple[str, str]:
    if mode != "llm":
        return "scripted", "scripted"
    if (client or get_client()) is None:
        return "scripted", "scripted (no API key)"
    return "llm", "llm"


class Orchestrator:
    def __init__(self, scope: TenantScope, mode: str = "scripted", bus: EventBus | None = None, client=None):
        self.scope = scope
        self.bus = bus or BUS
        self.client = client
        self.mode, self.mode_label = effective_mode(mode, client)

    # ---------------------------------------------------------------- nodes
    def _llm(self, run: AgentRun, mod, role: str, task: str, tools: list[str]) -> bool:
        r = run_llm_agent(run, mod.NAME, role, task, tools, client=self.client)
        if not r["ok"]:
            run.emit(mod.NAME, "message", summary=f"LLM {mod.NAME} fell back to scripted ({r['reason']})",
                     data={"fallback": True})
        return r["ok"]

    def build(self, run: AgentRun, event: dict):
        llm = self.mode == "llm"

        def n_sentinel(state: IncidentState):
            if llm:
                self._llm(run, sentinel, sentinel.ROLE, sentinel.task(event, run.incident_id), sentinel.TOOLS)
            if not get_incident(run.scope, run.incident_id) or not run.last("recall_similar_episodes"):
                sentinel.run_scripted(run, event)
            run.handoff("sentinel", "analyst", "incident opened; compute impact")
            run.handoff("sentinel", "comms", "incident opened; find owners and contracts")
            return {"incident_id": run.incident_id}

        def n_analyst(state: IncidentState):
            if llm:
                self._llm(run, analyst, analyst.ROLE, analyst.task(run.incident_id), analyst.TOOLS)
            inc = get_incident(run.scope, run.incident_id)
            if inc["incident"].get("revenue_at_risk_initial") is None:
                analyst.run_scripted(run)
            run.handoff("analyst", "planner", inc["incident"].get("impact_summary") or "impact computed")
            return {}

        def n_comms_prefetch(state: IncidentState):
            if llm:
                self._llm(run, comms, comms.ROLE, comms.task_prefetch(run.incident_id),
                          ["who_owns", "who_knows", "contract_terms", "doc_search"])
            if get_incident(run.scope, run.incident_id)["incident"].get("owner_ids") is None:
                comms.prefetch_scripted(run)
            run.handoff("comms", "planner", "owners and contract terms on the blackboard")
            return {}

        def n_planner(state: IncidentState):
            dtype = get_incident(run.scope, run.incident_id)["disruption"]["type"]
            if llm:
                self._llm(run, planner, planner.ROLE, planner.task(run.incident_id, dtype), planner.TOOLS)
            if not run.scope.ops.run("incident_actions", {"iid": run.incident_id}):
                planner.run_scripted(run)
            run.handoff("planner", "comms", "actions proposed; notify and summarise")
            return {}

        def n_comms(state: IncidentState):
            if llm:
                self._llm(run, comms, comms.ROLE, comms.task_final(run.incident_id), comms.TOOLS)
            summary = comms.final_scripted(run)
            run.emit("comms", "done", summary=summary, node_ids=[run.incident_id],
                     data={"mode": self.mode_label})
            return {}

        g = StateGraph(IncidentState)
        g.add_node("sentinel", n_sentinel)
        g.add_node("analyst", n_analyst)
        g.add_node("comms_prefetch", n_comms_prefetch)
        g.add_node("planner", n_planner)
        g.add_node("comms", n_comms)
        g.add_edge(START, "sentinel")
        g.add_edge("sentinel", "analyst")
        g.add_edge("sentinel", "comms_prefetch")
        g.add_edge(["analyst", "comms_prefetch"], "planner")
        g.add_edge("planner", "comms")
        g.add_edge("comms", END)
        return g.compile()

    # ---------------------------------------------------------------- run
    def run(self, event: dict, incident_id: str | None = None) -> str:
        did, iid = prepare(self.scope, event)
        iid = incident_id or iid
        self.bus.reset(iid)
        run = AgentRun(self.scope, iid, self.mode, self.bus)
        run.emit("orchestrator", "message", summary=f"Starting {self.mode_label} run for {event.get('name') or event}",
                 data={"mode": self.mode_label, "event": event})
        t0 = time.time()
        try:
            self.build(run, event).invoke({"tenant_id": self.scope.tenant_id, "incident_id": iid,
                                           "disruption_id": did, "event": event, "mode": self.mode})
        except Exception as e:  # noqa: BLE001
            run.emit("orchestrator", "error", summary=f"run failed: {e}", data={"fatal": True})
            raise
        finally:
            self.scope.save()
        self.last_seconds = round(time.time() - t0, 2)
        return iid

    def start(self, event: dict) -> tuple[str, threading.Thread]:
        """Run in a background thread; returns the incident id immediately."""
        _, iid = prepare(self.scope, event)
        self.bus.reset(iid)
        t = threading.Thread(target=self._safe_run, args=(event, iid), daemon=True)
        t.start()
        return iid, t

    def _safe_run(self, event: dict, iid: str) -> None:
        try:
            self.run(event, iid)
        except Exception:  # noqa: BLE001 - already emitted as an error event
            pass


def run_incident(scope: TenantScope, event: dict, mode: str = "scripted", client=None) -> str:
    return Orchestrator(scope, mode, client=client).run(event)
