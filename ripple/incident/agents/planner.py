"""The planner: proposes decision groups and options. It never ranks or chooses - Jev does."""

from __future__ import annotations

from ripple.incident import validate
from ripple.incident.agents.common import ask_validated, state_message
from ripple.incident.models import AnalystReport, CommsReport, EventRecord, EvidenceReport, PlannerTurn
from ripple.llm.base import LLMClient

AGENT = "planner"


def plan(client: LLMClient, event: EventRecord, report: EvidenceReport, analysis: AnalystReport,
         comms: CommsReport, emit) -> PlannerTurn:
    blocks = {"event": event.model_dump(), "evidence_report": report.model_dump(),
              "impact_report": analysis.model_dump(),
              "drafted_messages": [{"id": d.id, "to": d.recipient_role, "subject": d.subject, "purpose": d.purpose}
                                   for d in comms.drafts]}
    eids = {e.id for e in report.evidence}
    cids = {d.id for d in comms.drafts}
    return ask_validated(client, PlannerTurn, AGENT, AGENT,
                         [state_message("Evidence, impact and drafts", blocks, "Propose the decision groups.")],
                         lambda p: validate.plan(p.decision_groups, eids, cids), emit)
