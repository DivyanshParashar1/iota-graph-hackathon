"""The analyst: sizes the impact from the evidence report. Numbers only - no options, no priority."""

from __future__ import annotations

from ripple.incident import validate
from ripple.incident.agents.common import ask_validated, state_message
from ripple.incident.models import AnalystReport, EventRecord, EvidenceReport
from ripple.llm.base import LLMClient

AGENT = "analyst"


def analyse(client: LLMClient, event: EventRecord, report: EvidenceReport, emit) -> AnalystReport:
    blocks = {"event": event.model_dump(), "evidence_report": report.model_dump()}
    return ask_validated(client, AnalystReport, AGENT, AGENT,
                         [state_message("The evidence report", blocks, "Write the impact report.")],
                         lambda a: validate.analyst_report(a, report), emit)
