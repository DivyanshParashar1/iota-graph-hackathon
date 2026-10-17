"""Every artifact of the incident pipeline, as pydantic models.

As in `ripple/onboarding/models.py`, these are the JSON schema sent to each LLM agent, the validation of what
comes back, and the shape the UI reads. The agents' structured replies are the `*Turn` / `*Report` models; the
`DecisionPacket` is assembled from them in code (no LLM) and is what `ripple.decide.compile` turns into a Jev
request. None of these models carries a decision: probabilities and verdicts live in `ripple.decide`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ripple.onboarding.models import Model

EvidenceConfidence = Literal["fact", "ballpark", "synthetic", "unknown"]
IncidentStatus = Literal["received", "consulting", "analysing", "planning", "deciding", "auto_approved",
                         "awaiting_approval", "resolved", "failed"]
OptionStatus = Literal["auto_approved", "approved", "pending", "not_selected", "rejected", "superseded"]


# --------------------------------------------------------------------------- the event

class EventRecord(Model):
    """What a webhook reported, as stored on the incident."""

    id: str = ""
    kind: str = "event"
    summary: str
    source: str = "webhook"
    received_at: str = ""
    raw: dict = Field(default_factory=dict)


# --------------------------------------------------------------------------- orchestrator <-> experts

class ExpertAsk(Model):
    expert: str  # the role's machine name
    question: str
    why: str = ""  # what the orchestrator needs this for


class OrchestratorTurn(Model):
    """The orchestrator's questions for one round. It chooses what to ask; Jev chose whom it may ask."""

    note: str = ""  # one line: what this round is trying to establish
    asks: list[ExpertAsk] = Field(default_factory=list)


class Exchange(Model):
    """One question and an expert's answer."""

    round: int
    expert: str
    question: str
    why: str = ""
    answer: str = ""
    ok: bool = True
    node_ids: list[str] = Field(default_factory=list)  # ids that came back from the expert's tools


class Evidence(Model):
    id: str  # E1, E2, ...
    from_agent: str  # the expert the claim came from
    claim: str
    node_ids: list[str] = Field(default_factory=list)
    confidence: EvidenceConfidence = "fact"


class EvidenceReport(Model):
    """The orchestrator's funnel: everything the experts established, as numbered, sourced claims."""

    situation: str
    evidence: list[Evidence] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- analyst and comms

class Metric(Model):
    name: str
    value: float | str
    unit: str = ""
    basis_evidence_ids: list[str] = Field(default_factory=list)


class AnalystReport(Model):
    impact_summary: str
    metrics: list[Metric] = Field(default_factory=list)
    time_to_impact_hours: float | None = None
    affected_node_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class CommsDraft(Model):
    id: str  # C1, C2, ...
    recipient_role: str
    recipient_node_id: str | None = None
    channel: str = "email"
    subject: str
    body: str
    purpose: str = ""
    required_by_option_ids: list[str] = Field(default_factory=list)  # filled in from the plan


class CommsReport(Model):
    drafts: list[CommsDraft] = Field(default_factory=list)
    notes: str = ""


# --------------------------------------------------------------------------- planner

class Option(Model):
    id: str
    title: str
    action_kind: str  # free text, the way the industry names it: "reroute", "spot purchase", "hold", ...
    steps: list[str] = Field(default_factory=list)
    reversible: bool = True
    time_to_effect_hours: float | None = None
    cost_estimate: str = ""
    risk: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    alternative_to: str | None = None  # display only: the option this is a fallback for
    comms_ids: list[str] = Field(default_factory=list)
    is_wait: bool = False  # the "hold and gather more information" option of an exclusive group


class DecisionGroup(Model):
    id: str
    question: str
    mode: Literal["exclusive", "independent"]  # exclusive -> one Jev choice; independent -> one noul per option
    options: list[Option] = Field(default_factory=list)


class PlannerTurn(Model):
    summary: str
    decision_groups: list[DecisionGroup] = Field(default_factory=list)


# --------------------------------------------------------------------------- the packet Jev decides on

class DecisionPacket(Model):
    event: EventRecord
    evidence: list[Evidence] = Field(default_factory=list)
    analysis: AnalystReport
    comms: list[CommsDraft] = Field(default_factory=list)
    decision_groups: list[DecisionGroup] = Field(default_factory=list)

    def option(self, option_id: str) -> tuple[DecisionGroup, Option] | tuple[None, None]:
        for g in self.decision_groups:
            for o in g.options:
                if o.id == option_id:
                    return g, o
        return None, None

    def evidence_by_id(self) -> dict[str, Evidence]:
        return {e.id: e for e in self.evidence}


def is_wait(o: Option) -> bool:
    return o.is_wait or o.action_kind.strip().lower() in ("hold", "wait")
