"""The orchestrator: questions the experts, round by round, then funnels their answers into one evidence report.

It generates questions and the report. It does not choose which experts to consult (a Jev noul per role, in
`pipeline.consult_experts`) or when to stop asking (a Jev noul after each round) - those are decisions.
"""

from __future__ import annotations

from ripple.incident import validate
from ripple.incident.agents.common import ask_validated, state_message
from ripple.incident.models import EventRecord, EvidenceReport, Exchange, OrchestratorTurn
from ripple.llm.base import LLMClient
from ripple.onboarding.models import ExpertRole

AGENT = "orchestrator"


def _roster(roles: list[ExpertRole]) -> list[dict]:
    return [{"name": r.name, "title": r.title, "mandate": r.mandate, "works_on": r.focus_types,
             "can_answer": r.playbook[:4]} for r in roles]


def _transcript(exchanges: list[Exchange]) -> list[dict]:
    return [{"round": x.round, "expert": x.expert, "question": x.question, "answer": x.answer,
             "answered": x.ok, "node_ids": x.node_ids[:40]} for x in exchanges]


def plan_round(client: LLMClient, event: EventRecord, roles: list[ExpertRole], exchanges: list[Exchange],
               round_no: int, max_rounds: int, max_asks: int, emit) -> OrchestratorTurn:
    blocks = {"event": event.model_dump(), "experts_you_may_ask": _roster(roles),
              "round": round_no, "max_rounds": max_rounds, "transcript_so_far": _transcript(exchanges)}
    instruction = (f"Write the questions for round {round_no} of at most {max_rounds}, at most {max_asks} of them."
                   if exchanges else
                   f"Round 1 of at most {max_rounds}. Write the first questions, at most {max_asks} of them.")
    allowed = {r.name for r in roles}
    return ask_validated(client, OrchestratorTurn, AGENT, AGENT,
                         [state_message("The event and the experts", blocks, instruction)],
                         lambda t: validate.orchestrator_turn(t, allowed, max_asks), emit)


def write_report(client: LLMClient, event: EventRecord, exchanges: list[Exchange], emit) -> EvidenceReport:
    experts = {x.expert for x in exchanges}
    seen = {n for x in exchanges for n in x.node_ids}
    blocks = {"event": event.model_dump(), "transcript": _transcript(exchanges)}
    return ask_validated(client, EvidenceReport, AGENT, "orchestrator_report",
                         [state_message("The investigation", blocks, "Write the evidence report.")],
                         lambda r: validate.evidence_report(r, experts, seen), emit)
