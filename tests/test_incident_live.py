"""The live half of the incident pipeline: real LLM calls (`-m llm`) and real Jev calls (`-m jev`).

    .venv/bin/pytest -q -m llm -k incident             # each incident agent's prompt returns usable output
    .venv/bin/pytest -q -m jev                          # Jev answers our requests; the precedent eval
    .venv/bin/pytest -q -m "llm and jev and slow"       # one whole incident, webhook to decision

Jev needs JEV_API_KEY, or OPENROUTER_API_KEY (the default base URL is OpenRouter's). Every raw Jev response is
written to artifacts/jev_runs/<ts>/ - the first run is how the response shape gets pinned in
reference/JEV_VERIFIED.md.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from ripple import ROOT
from ripple.config import get_settings
from ripple.decide import calibrate
from ripple.decide import precedents as prec
from ripple.decide.compile import decision_request, relevance_request, sufficiency_request
from ripple.decide.jev import get_jev_client, set_jev_client
from ripple.graph.apply import apply_spec, load_instances
from ripple.incident import pipeline
from ripple.incident.agents import analyst, comms, orchestrator, planner
from ripple.incident.models import (
    AnalystReport,
    CommsReport,
    DecisionPacket,
    EventRecord,
    EvidenceReport,
    Exchange,
    is_wait,
)
from ripple.llm.base import get_client, set_client
from ripple.onboarding import store
from tests import factories as f

RUN = time.strftime("%Y%m%d-%H%M%S")
EVENT = EventRecord(id="INC-LIVE", kind="supplier_site_fire", source="site-alerts",
                    summary=f.event()["summary"], received_at="2026-10-17T06:42:00Z")


def noop(*_a, **_k) -> None:
    return None


def record(kind: str, name: str, payload) -> None:
    d = ROOT / "artifacts" / kind / RUN
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.json").write_text(json.dumps(payload, default=str, indent=2))


@pytest.fixture(scope="module")
def llm_env():
    os.environ.pop("RIPPLE_LLM_PROVIDER", None)
    os.environ["RIPPLE_LLM_LOG_DIR"] = str(ROOT / "artifacts" / "llm_runs" / RUN)
    get_settings.cache_clear()
    set_client(None)
    if not get_settings().has_llm:
        pytest.skip("no LLM provider configured (install the `claude` CLI or set a key)")
    yield get_client()
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def jev_env():
    """The real Jev. The suite blanks the keys so a developer's .env cannot leak into offline tests; here they are
    removed so .env applies again."""
    for k in ("JEV_API_KEY", "OPENROUTER_API_KEY"):
        os.environ.pop(k, None)
    get_settings.cache_clear()
    set_jev_client(None)
    if not get_settings().has_jev:
        pytest.skip("no Jev key (set JEV_API_KEY or OPENROUTER_API_KEY)")
    yield get_jev_client()
    os.environ.update(JEV_API_KEY="", OPENROUTER_API_KEY="")
    get_settings.cache_clear()


def transcript() -> list[Exchange]:
    return [Exchange(round=1, expert="sourcing_risk", question="Who supplies PRT-0001, at what share and lead time?",
                     answer="PRT-0001 (Sole) is supplied by SUP-0001 GZ Leather (CN) at 60% of volume with a 30-day "
                            "lead time, and by SUP-0002 Rubber Co (VN) at 40% with a 21-day lead time. SUP-0002's "
                            "row is marked ballpark.",
                     node_ids=["SUP-0001", "SUP-0002", "PRT-0001"])]


# --------------------------------------------------------------------------- each prompt returns usable output

@pytest.mark.llm
def test_incident_orchestrator_prompt_asks_answerable_questions(llm_env):
    turn = orchestrator.plan_round(llm_env, EVENT, [f.role(status="approved")], [], 1, 4, 6, noop)
    assert turn.asks and {a.expert for a in turn.asks} == {"sourcing_risk"}
    record("llm_runs", "orchestrator_turn", turn.model_dump())


@pytest.mark.llm
def test_incident_report_prompt_keeps_to_the_transcript(llm_env):
    rep = orchestrator.write_report(llm_env, EVENT, transcript(), noop)
    assert rep.evidence and all(set(e.node_ids) <= {"SUP-0001", "SUP-0002", "PRT-0001"} for e in rep.evidence)
    record("llm_runs", "evidence_report", rep.model_dump())


@pytest.mark.llm
def test_incident_analyst_and_comms_prompts(llm_env):
    rep = EvidenceReport.model_validate(f.report())
    a = analyst.analyse(llm_env, EVENT, rep, noop)
    c = comms.draft(llm_env, EVENT, rep, "Acme Shoes", noop)
    assert a.metrics and all(m.basis_evidence_ids for m in a.metrics)
    assert c.drafts
    record("llm_runs", "analysis", a.model_dump())
    record("llm_runs", "comms", c.model_dump())


@pytest.mark.llm
def test_incident_planner_prompt_proposes_without_choosing(llm_env):
    p = planner.plan(llm_env, EVENT, EvidenceReport.model_validate(f.report()),
                     AnalystReport.model_validate(f.analysis()), CommsReport.model_validate(f.comms()), noop)
    excl = [g for g in p.decision_groups if g.mode == "exclusive"]
    assert excl and all(sum(is_wait(o) for o in g.options) == 1 for g in excl)
    text = json.dumps(p.model_dump()).lower()
    assert "probability" not in text and "recommend" not in text
    record("llm_runs", "plan", p.model_dump())


# --------------------------------------------------------------------------- Jev answers our requests

@pytest.mark.jev
def test_jev_answers_the_scenario_packet(jev_env):
    packet = DecisionPacket.model_validate(f.scenario()["decision_packet"])
    req, qmap = decision_request(packet, prec.nearest(packet.event.kind, packet.event.summary))
    res = jev_env.decide(req)
    record("jev_runs", "scenario", {"request": req.model_dump(), "raw": res.raw,
                                    "answers": {k: a.model_dump() for k, a in res.answers.items()}})
    assert set(res.answers) == set(req.questions)
    for a in res.answers.values():
        assert sum(a.probabilities.values()) == pytest.approx(1.0, abs=0.05)
    assert res[qmap.priority].top in ("low", "medium", "high", "critical")


@pytest.mark.jev
def test_jev_answers_relevance_and_sufficiency(jev_env):
    req, names = relevance_request(EVENT, [f.role()])
    res = jev_env.decide(req)
    assert set(res.answers) == set(names)
    res2 = jev_env.decide(sufficiency_request(EVENT, transcript()))
    assert 0.0 <= res2["sufficient"].p_true <= 1.0
    record("jev_runs", "relevance_sufficiency", {"relevance": res.raw, "sufficiency": res2.raw})


@pytest.mark.jev
@pytest.mark.slow
def test_jev_mostly_agrees_with_what_worked(jev_env):
    out = calibrate.evaluate(jev_env)
    record("jev_runs", "precedents", out)
    assert out["errors"] == 0
    assert out["agreement"] >= 0.6, out  # the heuristics come from these cases, so this is an upper bound


# --------------------------------------------------------------------------- one whole incident

@pytest.mark.llm
@pytest.mark.jev
@pytest.mark.slow
def test_a_whole_incident_live(db, llm_env, jev_env, request):
    from ripple.db import TenantScope
    from tests.conftest import tenant_id_for

    scope = TenantScope(tenant_id_for(request.node.name), db)
    scope.drop()
    store.create_tenant(scope, "Acme Shoes", "footwear")
    spec = f.spec()
    row = store.save_spec(scope, spec)
    store.set_spec_status(scope, row["id"], "approved")
    apply_spec(scope, spec)
    load_instances(scope, spec, f.batch())
    store.save_expert(scope, f.role(status="approved"))
    inc = pipeline.receive(scope, f.event())
    pipeline.run(scope, inc["id"], client=llm_env, jev=jev_env)
    d = pipeline.detail(scope, inc["id"])
    record("jev_runs", "incident", d)
    assert d["incident"]["status"] in ("auto_approved", "awaiting_approval"), d["incident"].get("error")
    assert d["jev"][0]["purpose"] == "relevance" and d["jev"][-1]["purpose"] == "decision"
    assert d["groups"] and d["incident"]["priority"]
