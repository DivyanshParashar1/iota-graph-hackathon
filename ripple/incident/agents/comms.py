"""The comms agent: drafts one message per recipient the response may need. Nothing is sent from here."""

from __future__ import annotations

from ripple.incident import validate
from ripple.incident.agents.common import ask_validated, state_message
from ripple.incident.models import CommsReport, EventRecord, EvidenceReport
from ripple.llm.base import LLMClient

AGENT = "comms"


def draft(client: LLMClient, event: EventRecord, report: EvidenceReport, company: str, emit) -> CommsReport:
    blocks = {"company": company, "event": event.model_dump(), "evidence_report": report.model_dump()}
    return ask_validated(client, CommsReport, AGENT, AGENT,
                         [state_message("The evidence report", blocks, f"Draft the messages, writing as {company}.")],
                         lambda c: validate.comms_report(c, report), emit)
