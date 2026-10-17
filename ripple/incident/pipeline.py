"""The incident pipeline: webhook -> orchestrator <-> experts -> analyst || comms -> planner -> Jev -> policy.

    receive(scope, body)            normalise a webhook body into an `_Incident` (status `received`)
    run(scope, incident_id)         run every stage; the incident ends `auto_approved`, `awaiting_approval`
                                    or `failed`
    approve / reject                a person acts on an option (an exclusive group keeps one approved option)
    detail(scope, incident_id)      everything the UI shows, including each approved option's live impact

The rule (docs/m8_decision_pipeline.md §1): only Jev decides. The three places a decision is needed before the
final one - which experts to consult, when to stop asking, and (with the options) the event's priority - are
Jev questions. The LLM agents generate questions, evidence, numbers, drafts and options. Policy thresholds on
Jev's probabilities decide whether a person has to approve.

Every stage's artifact is written to the incident as soon as it exists, and every step goes to the bus and the
`_AgentStep` trail under stage `incident`, so the UI can follow a run live and rebuild it after a reload.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from ripple.config import get_settings
from ripple.db import TenantScope
from ripple.decide import policy
from ripple.decide import precedents as prec
from ripple.decide.compile import decision_request, relevance_request, sufficiency_request
from ripple.decide.jev import DecisionModel, JevError, JevRequest, JevResult, get_jev_client
from ripple.experts import runtime
from ripple.incident import store
from ripple.incident.agents import analyst, comms, orchestrator, planner
from ripple.incident.agents.common import AgentFailed
from ripple.incident.models import (
    AnalystReport,
    CommsReport,
    DecisionPacket,
    EventRecord,
    EvidenceReport,
    Exchange,
    PlannerTurn,
)
from ripple.llm.base import LLMClient, LLMError, get_client
from ripple.onboarding.events import BUS, StepEmitter
from ripple.onboarding.models import ExpertRole
from ripple.onboarding.store import get_tenant, list_experts

log = logging.getLogger("ripple.incident")
STAGE = "incident"
EXPERT_WORKERS = 4
APPROVED = ("approved", "auto_approved")


class PipelineError(RuntimeError):
    """The pipeline cannot run for this tenant (no approved experts, nothing to ask)."""


def _emitter(scope: TenantScope, agent: str) -> StepEmitter:
    return StepEmitter(scope, STAGE, agent)


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- intake

def receive(scope: TenantScope, body: dict) -> dict:
    """A webhook body -> a new incident. Any JSON object with a free-text `summary` (or `text`, `message`,
    `description`) is accepted; `kind`/`type`, `source` and `received_at` are optional; the whole body is kept
    as `raw`. Raises ValueError when there is no text to work from."""
    if not isinstance(body, dict):
        raise ValueError("the event must be a JSON object")
    summary = next((str(body[k]).strip() for k in ("summary", "text", "message", "description")
                    if isinstance(body.get(k), str) and body[k].strip()), "")
    if not summary:
        raise ValueError("the event needs a free-text `summary`")
    event = EventRecord(kind=str(body.get("kind") or body.get("type") or "event")[:80], summary=summary[:4000],
                        source=str(body.get("source") or "webhook")[:80],
                        received_at=str(body.get("received_at") or _now_iso())[:40], raw=body)
    inc = store.create_incident(scope, event)
    _emitter(scope, "webhook")("write", f"event received: {summary[:160]}", data={"incident": inc["id"]})
    return inc


# --------------------------------------------------------------------------- Jev calls

def _ask_jev(scope: TenantScope, iid: str, jev: DecisionModel, purpose: str, req: JevRequest, emit) -> JevResult:
    res = jev.decide(req)
    store.record_jev(scope, iid, purpose, req.model_dump(), {k: a.model_dump() for k, a in res.answers.items()},
                     res.model or jev.model, res.ms)
    emit("decision", f"jev: {purpose}", ms=res.ms,
         data={"incident": iid, "purpose": purpose,
               "answers": {k: {"top": a.top, "p": round(a.p(a.top), 3)} for k, a in res.answers.items()}})
    return res


def choose_experts(scope: TenantScope, iid: str, event: EventRecord, roles: list[ExpertRole], jev: DecisionModel,
                   emit, settings=None) -> list[ExpertRole]:
    """Jev answers, per approved role, whether it is relevant. Roles at or over the threshold are consulted; if
    none is, the role Jev rates most relevant is (its own ranking, not a model's choice)."""
    s = settings or get_settings()
    req, names = relevance_request(event, roles)
    res = _ask_jev(scope, iid, jev, "relevance", req, emit)
    probs = {names[q]: res[q].p_true for q in names}
    chosen = [r for r in roles if probs[r.name] >= s.ripple_expert_relevance_min]
    if not chosen:
        chosen = [max(roles, key=lambda r: (probs[r.name], r.name))]
    store.set_incident(scope, iid, relevant=[{"name": r.name, "title": r.title, "p": probs[r.name],
                                              "consulted": r in chosen} for r in roles])
    return chosen


def consult(scope: TenantScope, iid: str, event: EventRecord, roles: list[ExpertRole], client: LLMClient,
            jev: DecisionModel, settings=None) -> list[Exchange]:
    """The orchestrator <-> experts loop. The orchestrator writes each round's questions; experts answer in
    parallel from the graph; Jev judges after every round whether the evidence suffices. Hard cap on rounds."""
    s = settings or get_settings()
    emit = _emitter(scope, orchestrator.AGENT)
    by_name = {r.name: r for r in roles}
    exchanges: list[Exchange] = []
    for round_no in range(1, s.ripple_incident_max_rounds + 1):
        turn = orchestrator.plan_round(client, event, roles, exchanges, round_no, s.ripple_incident_max_rounds,
                                       s.ripple_incident_max_asks, emit)
        if not turn.asks:
            emit("llm", "orchestrator: no further questions", data={"incident": iid, "round": round_no})
            break
        emit("llm", f"round {round_no}: {len(turn.asks)} questions" + (f" - {turn.note}" if turn.note else ""),
             data={"incident": iid, "asks": [a.model_dump() for a in turn.asks]})

        def ask(a, round_no=round_no) -> Exchange:
            role = by_name[a.expert]
            ex_emit = _emitter(scope, role.name)
            out = runtime.ask(scope, role, a.question, client=client,
                              on_step=lambda ev, e=ex_emit: e(ev["kind"], ev.get("summary") or ev.get("tool") or "",
                                                              data={"incident": iid}))
            return Exchange(round=round_no, expert=role.name, question=a.question, why=a.why,
                            answer=out.get("text") or out.get("reason") or "", ok=bool(out.get("ok")),
                            node_ids=list(out.get("ids") or []))

        with ThreadPoolExecutor(max_workers=min(EXPERT_WORKERS, len(turn.asks))) as pool:
            exchanges += list(pool.map(ask, turn.asks))
        store.set_incident(scope, iid, exchanges=[x.model_dump() for x in exchanges])
        res = _ask_jev(scope, iid, jev, "sufficiency", sufficiency_request(event, exchanges), emit)
        if res["sufficient"].p_true >= s.ripple_evidence_sufficient_min:
            break
        if round_no == s.ripple_incident_max_rounds:
            emit("llm", f"round cap ({round_no}) reached; reporting what is known", data={"incident": iid})
    if not exchanges:
        raise PipelineError("the orchestrator asked the experts nothing")
    return exchanges


def analyse_and_draft(scope: TenantScope, event: EventRecord, report: EvidenceReport,
                      client: LLMClient) -> tuple[AnalystReport, CommsReport]:
    """The analyst and the comms agent, in parallel, each from the full evidence report."""
    company = (get_tenant(scope) or {}).get("name") or scope.tenant_id
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(analyst.analyse, client, event, report, _emitter(scope, analyst.AGENT))
        fc = pool.submit(comms.draft, client, event, report, company, _emitter(scope, comms.AGENT))
        return fa.result(), fc.result()


def assemble(event: EventRecord, report: EvidenceReport, analysis: AnalystReport, comms_rep: CommsReport,
             plan: PlannerTurn) -> DecisionPacket:
    """The packet Jev decides on, built in code from the agents' outputs. Each draft learns which options use it."""
    used: dict[str, list[str]] = {}
    for g in plan.decision_groups:
        for o in g.options:
            for c in o.comms_ids:
                used.setdefault(c, []).append(o.id)
    drafts = [d.model_copy(update={"required_by_option_ids": used.get(d.id, [])}) for d in comms_rep.drafts]
    return DecisionPacket(event=event, evidence=report.evidence, analysis=analysis, comms=drafts,
                          decision_groups=plan.decision_groups)


def decide(scope: TenantScope, iid: str, packet: DecisionPacket, jev: DecisionModel,
           settings=None) -> policy.Outcome:
    """Jev on the packet, then the policy. Writes options, auto-approvals and the incident's final status."""
    s = settings or get_settings()
    emit = _emitter(scope, "jev")
    near = prec.nearest(packet.event.kind, packet.event.summary, k=3)
    req, qmap = decision_request(packet, near)
    res = _ask_jev(scope, iid, jev, "decision", req, emit)
    outcome = policy.apply(packet, res, qmap, policy.Thresholds.from_settings(s))
    verdicts = outcome.by_option()
    for g in packet.decision_groups:
        for o in g.options:
            v = verdicts[o.id]
            store.save_option(scope, iid, option=o.model_dump(), group_id=g.id, mode=g.mode,
                              probability=v.probability, rank=v.rank, status=v.status, reason=v.reason)
            if v.status == "auto_approved":
                store.record_approval(scope, iid, o.id, actor="jev-policy", action="approve", note=outcome.reason)
    status = "auto_approved" if outcome.auto else "awaiting_approval"
    store.set_incident(scope, iid, priority=outcome.priority, auto=outcome.auto, status=status,
                       outcome={**outcome.to_dict(), "precedents": [r["id"] for r in near]},
                       qmap=qmap.to_dict())
    emit("decision", f"priority {outcome.priority}: {outcome.reason}",
         data={"incident": iid, "auto": outcome.auto,
               "approved": [v.option_id for v in outcome.verdicts if v.status == "auto_approved"]})
    return outcome


# --------------------------------------------------------------------------- the run

def run(scope: TenantScope, iid: str, *, client: LLMClient | None = None, jev: DecisionModel | None = None,
        settings=None) -> dict:
    s = settings or get_settings()
    inc = store.get_incident(scope, iid)
    if inc is None:
        raise KeyError(f"no incident {iid}")
    event = store.event_of(inc)
    emit = _emitter(scope, "pipeline")
    BUS.enter(scope.tenant_id)
    try:
        client = client or get_client()
        jev = jev or get_jev_client(s)
        roles = [r for r in list_experts(scope) if r.status == "approved"]
        if not roles:
            raise PipelineError("no approved expert roles: finish onboarding first")
        store.set_incident(scope, iid, status="consulting", error="")
        emit("stage", "consulting the experts", data={"incident": iid})
        chosen = choose_experts(scope, iid, event, roles, jev, _emitter(scope, "jev"), s)
        exchanges = consult(scope, iid, event, chosen, client, jev, s)

        store.set_incident(scope, iid, status="analysing")
        emit("stage", "writing the evidence report", data={"incident": iid})
        report = orchestrator.write_report(client, event, exchanges, _emitter(scope, orchestrator.AGENT))
        store.set_incident(scope, iid, report=report.model_dump())
        store.link_concerns(scope, iid, [n for e in report.evidence for n in e.node_ids])
        analysis, comms_rep = analyse_and_draft(scope, event, report, client)
        store.set_incident(scope, iid, analysis=analysis.model_dump(), comms=comms_rep.model_dump())

        store.set_incident(scope, iid, status="planning")
        emit("stage", "planning", data={"incident": iid})
        plan = planner.plan(client, event, report, analysis, comms_rep, _emitter(scope, planner.AGENT))
        packet = assemble(event, report, analysis, comms_rep, plan)
        store.set_incident(scope, iid, plan=plan.model_dump(), packet=packet.model_dump(), status="deciding")

        emit("stage", "deciding", data={"incident": iid})
        outcome = decide(scope, iid, packet, jev, s)
        emit("done", f"incident {iid}: {outcome.priority}, " + ("auto-approved" if outcome.auto else
                                                                 "awaiting approval"), data={"incident": iid})
    except Exception as e:  # a failed run is recorded on the incident, never lost
        expected = isinstance(e, LLMError | JevError | AgentFailed | PipelineError)
        if expected:
            log.warning("incident %s failed: %s", iid, e)
        else:
            log.exception("incident %s failed", iid)
        store.set_incident(scope, iid, status="failed", error=f"{type(e).__name__}: {e}"[:2000])
        emit("error", f"incident {iid} failed: {e}",
             data={"incident": iid, "fatal": True, "bug": not expected, "error": type(e).__name__})
    finally:
        BUS.leave(scope.tenant_id)
    return store.get_incident(scope, iid) or {}


# --------------------------------------------------------------------------- people act on the options

def _packet(inc: dict) -> DecisionPacket:
    if not inc.get("packet"):
        raise PipelineError("this incident has no options yet")
    return DecisionPacket.model_validate(inc["packet"])


def _refresh_status(scope: TenantScope, iid: str) -> None:
    if not any(o["status"] == "pending" for o in store.list_options(scope, iid)):
        store.set_incident(scope, iid, status="resolved")


def approve(scope: TenantScope, iid: str, option_id: str, *, note: str = "", actor: str = "user") -> dict:
    """A person approves an option. In an exclusive group the other options stop being candidates: an earlier
    approval is superseded, the rest are not selected."""
    inc = store.get_incident(scope, iid)
    if inc is None:
        raise KeyError(f"no incident {iid}")
    g, o = _packet(inc).option(option_id)
    if o is None:
        raise KeyError(f"no option {option_id} in {iid}")
    current = {x["option_id"]: x for x in store.list_options(scope, iid)}
    if current.get(option_id, {}).get("status") not in APPROVED:
        store.set_option(scope, iid, option_id, status="approved", reason=f"approved by {actor}")
        store.record_approval(scope, iid, option_id, actor=actor, action="approve", note=note)
    if g.mode == "exclusive":
        for sib in g.options:
            if sib.id == option_id:
                continue
            st = current.get(sib.id, {}).get("status")
            if st in APPROVED:
                store.set_option(scope, iid, sib.id, status="superseded", reason=f"{option_id} approved by {actor}")
                store.record_approval(scope, iid, sib.id, actor=actor, action="supersede", note=note)
            elif st == "pending":
                store.set_option(scope, iid, sib.id, status="not_selected", reason=f"{option_id} approved instead")
    _emitter(scope, actor)("write", f"{iid}: {option_id} approved", data={"incident": iid})
    _refresh_status(scope, iid)
    return detail(scope, iid)


def reject(scope: TenantScope, iid: str, option_id: str, *, note: str = "", actor: str = "user") -> dict:
    """A person rejects an option - including one the policy auto-approved, which undoes that approval."""
    inc = store.get_incident(scope, iid)
    if inc is None:
        raise KeyError(f"no incident {iid}")
    _, o = _packet(inc).option(option_id)
    if o is None:
        raise KeyError(f"no option {option_id} in {iid}")
    store.set_option(scope, iid, option_id, status="rejected", reason=f"rejected by {actor}")
    store.record_approval(scope, iid, option_id, actor=actor, action="reject", note=note)
    _emitter(scope, actor)("write", f"{iid}: {option_id} rejected", data={"incident": iid})
    _refresh_status(scope, iid)
    return detail(scope, iid)


# --------------------------------------------------------------------------- what the UI shows

def impact(scope: TenantScope, inc: dict, options: list[dict]) -> list[dict]:
    """For each approved option: the graph nodes it touches as they are now, the metrics its evidence sizes,
    the messages it sends, and when it takes effect. Recomputed from the live graph on every read."""
    if not inc.get("packet"):
        return []
    packet = DecisionPacket.model_validate(inc["packet"])
    ev = packet.evidence_by_id()
    drafts = {d.id: d for d in packet.comms}
    approvals = {a["option_id"]: a for a in store.list_approvals(scope, inc["id"]) if a["action"] == "approve"}
    out = []
    for row in options:
        if row["status"] not in APPROVED:
            continue
        _, o = packet.option(row["option_id"])
        if o is None:
            continue
        node_ids = {n for i in o.evidence_ids if i in ev for n in ev[i].node_ids}
        node_ids |= {drafts[c].recipient_node_id for c in o.comms_ids if c in drafts and drafts[c].recipient_node_id}
        metrics = [m.model_dump() for m in packet.analysis.metrics if set(m.basis_evidence_ids) & set(o.evidence_ids)]
        approved_at = (approvals.get(o.id) or {}).get("ts")
        effective = None
        if approved_at and o.time_to_effect_hours is not None:
            effective = (datetime.fromtimestamp(approved_at / 1000, UTC)
                         + timedelta(hours=o.time_to_effect_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        out.append({"option_id": o.id, "title": o.title, "status": row["status"],
                    "nodes": store.nodes_by_ids(scope, sorted(node_ids)), "metrics": metrics,
                    "messages": [drafts[c].model_dump() for c in o.comms_ids if c in drafts],
                    "takes_effect_in_hours": o.time_to_effect_hours, "effective_at": effective,
                    "reversible": o.reversible})
    return out


def detail(scope: TenantScope, iid: str) -> dict:
    inc = store.get_incident(scope, iid)
    if inc is None:
        raise KeyError(f"no incident {iid}")
    options = store.list_options(scope, iid)
    by_id = {o["option_id"]: o for o in options}
    groups = []
    for g in (inc.get("packet") or {}).get("decision_groups") or []:
        groups.append({"id": g["id"], "question": g["question"], "mode": g["mode"],
                       "options": [{**o, **{k: by_id.get(o["id"], {}).get(k) for k in
                                            ("probability", "rank", "status", "reason")}}
                                   for o in g["options"]]})
    jev_calls = [{"id": d["id"], "purpose": d["purpose"], "model": d["model"], "ms": d["ms"], "ts": d["ts"],
                  "answers": d["result"],
                  "questions": {k: {"type": q.get("type"), "instructions": q.get("instructions")}
                                for k, q in (d["request"].get("questions") or {}).items()},
                  "state_chars": len(d["request"].get("state") or "")}
                 for d in store.list_jev(scope, iid)]
    return {"incident": inc, "groups": groups, "jev": jev_calls, "approvals": store.list_approvals(scope, iid),
            "impact": impact(scope, inc, options)}
