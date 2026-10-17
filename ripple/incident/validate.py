"""What makes an agent's structured reply unusable. Each function returns one message per problem; an agent
whose reply has problems is sent them back and asked again (see `agents/common.ask_validated`).

The checks are about referential integrity, not judgement: an expert that does not exist, a node id no tool
returned, an evidence id that is not in the report, an exclusive group with nothing to choose between.
"""

from __future__ import annotations

import re

from ripple.decide.jev import MAX_CHOICE_OPTIONS
from ripple.incident.models import (
    AnalystReport,
    CommsReport,
    DecisionGroup,
    EvidenceReport,
    OrchestratorTurn,
    is_wait,
)

ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,40}$")


def orchestrator_turn(turn: OrchestratorTurn, allowed_experts: set[str], max_asks: int) -> list[str]:
    errs: list[str] = []
    if len(turn.asks) > max_asks:
        errs.append(f"{len(turn.asks)} questions; at most {max_asks} per round")
    for a in turn.asks:
        if a.expert not in allowed_experts:
            errs.append(f"{a.expert!r} is not one of the experts you may ask: {sorted(allowed_experts)}")
        if not a.question.strip():
            errs.append(f"an empty question to {a.expert}")
    seen = set()
    for a in turn.asks:
        key = (a.expert, a.question.strip().lower())
        if key in seen:
            errs.append(f"the same question twice to {a.expert}")
        seen.add(key)
    return errs


def evidence_report(report: EvidenceReport, experts: set[str], seen_ids: set[str]) -> list[str]:
    errs: list[str] = []
    if not report.evidence:
        errs.append("no evidence: every claim the experts made that matters to the response must be listed")
    ids = [e.id for e in report.evidence]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        errs.append(f"duplicate evidence ids {dupes}")
    for e in report.evidence:
        if not ID_RE.match(e.id):
            errs.append(f"evidence id {e.id!r} must be short and plain, like E1")
        if e.from_agent not in experts:
            errs.append(f"{e.id}: from_agent {e.from_agent!r} is not an expert that was consulted")
        bad = sorted(set(e.node_ids) - seen_ids)
        if bad:
            errs.append(f"{e.id}: node ids {bad[:5]} did not come back from any expert's tools")
        if not e.claim.strip():
            errs.append(f"{e.id}: empty claim")
    return errs


def analyst_report(a: AnalystReport, report: EvidenceReport) -> list[str]:
    errs: list[str] = []
    eids = {e.id for e in report.evidence}
    nodes = {n for e in report.evidence for n in e.node_ids}
    if not a.impact_summary.strip():
        errs.append("no impact summary")
    for m in a.metrics:
        bad = sorted(set(m.basis_evidence_ids) - eids)
        if bad:
            errs.append(f"metric {m.name}: evidence {bad} is not in the report")
        if not m.basis_evidence_ids:
            errs.append(f"metric {m.name}: no basis - every number must rest on evidence ids")
    bad = sorted(set(a.affected_node_ids) - nodes)
    if bad:
        errs.append(f"affected_node_ids {bad[:5]} are not named by any evidence")
    if a.time_to_impact_hours is not None and a.time_to_impact_hours < 0:
        errs.append("time_to_impact_hours cannot be negative")
    return errs


def comms_report(c: CommsReport, report: EvidenceReport) -> list[str]:
    errs: list[str] = []
    nodes = {n for e in report.evidence for n in e.node_ids}
    ids = [d.id for d in c.drafts]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        errs.append(f"duplicate draft ids {dupes}")
    for d in c.drafts:
        if not ID_RE.match(d.id):
            errs.append(f"draft id {d.id!r} must be short and plain, like C1")
        if d.recipient_node_id and d.recipient_node_id not in nodes:
            errs.append(f"{d.id}: recipient_node_id {d.recipient_node_id!r} is not named by any evidence "
                        "(leave it null if the recipient is not in the graph)")
        if not d.body.strip() or not d.subject.strip():
            errs.append(f"{d.id}: a draft needs a subject and a body")
    return errs


def plan(groups: list[DecisionGroup], evidence_ids: set[str], comms_ids: set[str]) -> list[str]:
    errs: list[str] = []
    if not groups:
        errs.append("no decision groups")
    gids = [g.id for g in groups]
    if len(set(gids)) != len(gids):
        errs.append("duplicate group ids")
    oids = [o.id for g in groups for o in g.options]
    dupes = sorted({i for i in oids if oids.count(i) > 1})
    if dupes:
        errs.append(f"option ids must be unique across all groups: {dupes}")
    for g in groups:
        if not ID_RE.match(g.id):
            errs.append(f"group id {g.id!r} must be short and plain, like G1")
        waits = [o for o in g.options if is_wait(o)]
        if g.mode == "exclusive":
            if not 2 <= len(g.options) <= MAX_CHOICE_OPTIONS:
                errs.append(f"{g.id}: an exclusive group needs 2-{MAX_CHOICE_OPTIONS} options")
            if len(waits) != 1:
                errs.append(f"{g.id}: an exclusive group needs exactly one wait/hold option (is_wait: true), "
                            f"has {len(waits)}")
        else:
            if not g.options:
                errs.append(f"{g.id}: an independent group needs at least one action")
            if waits:
                errs.append(f"{g.id}: 'wait' is not an independent action - leave it out of independent groups")
        local = {o.id for o in g.options}
        for o in g.options:
            if not ID_RE.match(o.id):
                errs.append(f"option id {o.id!r} must be short and plain")
            bad = sorted(set(o.evidence_ids) - evidence_ids)
            if bad:
                errs.append(f"{o.id}: evidence {bad} is not in the report")
            if not o.evidence_ids and not is_wait(o):
                errs.append(f"{o.id}: no evidence_ids - every option must rest on the evidence")
            bad = sorted(set(o.comms_ids) - comms_ids)
            if bad:
                errs.append(f"{o.id}: comms {bad} were not drafted")
            if o.alternative_to and (o.alternative_to not in local or o.alternative_to == o.id):
                errs.append(f"{o.id}: alternative_to must name another option in the same group")
            if not o.title.strip():
                errs.append(f"{o.id}: no title")
    return errs
