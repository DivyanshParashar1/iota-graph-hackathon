"""The incident pipeline end to end, deterministically: the webhook, the orchestrator <-> expert loop, the analyst
and comms in parallel, the planner, Jev, the policy, approvals and live impact.

Both model boundaries are transport stubs that replay payloads written here: `StubClient` for the LLM agents
(dispatched on the schema each call asks for) and `JevTransport` for Jev (the real client over a mock HTTP
transport). Neither holds any product logic. Whether the agents' *prompts* produce usable output, and whether
Jev's answers are sensible, is the live suite's job (tests/test_incident_live.py).
"""

from __future__ import annotations

import time

import pytest

from ripple.config import get_settings
from ripple.decide.jev import set_jev_client
from ripple.graph.apply import apply_spec, load_instances
from ripple.incident import store as istore
from ripple.incident import validate
from ripple.incident.models import (
    AnalystReport,
    CommsReport,
    DecisionGroup,
    EventRecord,
    EvidenceReport,
    OrchestratorTurn,
)
from ripple.onboarding import store
from tests import factories as f

ASK = {"note": "establish exposure", "asks": [{"expert": "sourcing_risk", "question": "Who supplies PRT-0001, and "
                                               "at what share?", "why": "size the loss"}]}


def agents(turns=None, plans=None, expert_text="SUP-0001 and SUP-0002 supply the soles."):
    """A StubClient script item that answers each agent's call with a payload written here, chosen by the schema
    the call asks for. An expert call (tools, no schema) calls `find_nodes` once and then answers."""
    turns = list(turns or [ASK, {"asks": []}])
    plans = list(plans or [f.plan()])
    n = {"orch": 0, "plan": 0}

    def reply(call):
        title = (call["schema"] or {}).get("title")
        if title == "OrchestratorTurn":
            n["orch"] += 1
            return turns[min(n["orch"] - 1, len(turns) - 1)]
        if title == "EvidenceReport":
            return f.report()
        if title == "AnalystReport":
            return f.analysis()
        if title == "CommsReport":
            return f.comms()
        if title == "PlannerTurn":
            n["plan"] += 1
            return plans[min(n["plan"] - 1, len(plans) - 1)]
        last = call["messages"][-1]["content"]
        if isinstance(last, list) and any(b.get("type") == "tool_result" for b in last):
            return expert_text
        return ("", [("find_nodes", {"label": "Supplier"})])

    return reply


@pytest.fixture
def live(scope):
    """A tenant that has finished onboarding: an approved ontology, instance data, one approved expert."""
    spec = f.spec()
    row = store.save_spec(scope, spec)
    store.set_spec_status(scope, row["id"], "approved")
    apply_spec(scope, spec)
    load_instances(scope, spec, f.batch())
    store.save_expert(scope, f.role(status="approved"))
    return scope


@pytest.fixture
def settings_env(monkeypatch):
    """Set RIPPLE_* settings for one test."""

    def set_(**kw):
        for k, v in kw.items():
            monkeypatch.setenv(k, str(v))
        get_settings.cache_clear()

    yield set_
    get_settings.cache_clear()


def post_event(app_client, body=None, **params):
    return app_client.post(f"/api/events/{app_client.tenant_id}", json=body or f.event(),
                           params={"wait": "true", **params})


def options(detail) -> dict:
    return {o["id"]: o for g in detail["groups"] for o in g["options"]}


# --------------------------------------------------------------------------- the full run

def test_a_critical_event_runs_end_to_end_and_skips_the_human(app_client, stub, jev, live):
    stub.load(agents())
    jev.load(lambda body: f.jev_body(body, priority="critical", p_priority=0.85, noul=0.8))
    r = post_event(app_client)
    assert r.status_code == 200, r.text
    d = r.json()
    inc = d["incident"]
    assert inc["status"] == "auto_approved" and inc["priority"] == "critical" and inc["auto"] is True
    assert inc["relevant"][0] == {"name": "sourcing_risk", "title": "Sourcing Risk Analyst", "p": 0.8,
                                  "consulted": True}
    assert inc["exchanges"][0]["expert"] == "sourcing_risk" and inc["exchanges"][0]["ok"] is True
    assert set(inc["exchanges"][0]["node_ids"]) >= {"SUP-0001", "SUP-0002"}
    assert [j["purpose"] for j in d["jev"]] == ["relevance", "sufficiency", "decision"]

    o = options(d)
    assert o["G1_shift"]["status"] == "auto_approved" and o["G1_shift"]["rank"] == 1
    assert o["G1_wait"]["status"] == "not_selected"
    assert o["A_notify"]["status"] == o["A_reserve"]["status"] == "auto_approved"
    assert {a["actor"] for a in d["approvals"]} == {"jev-policy"}

    imp = {i["option_id"]: i for i in d["impact"]}
    assert set(imp) == {"G1_shift", "A_notify", "A_reserve"}
    assert [n["id"] for n in imp["G1_shift"]["nodes"]] == ["SUP-0002"]
    assert [m["name"] for m in imp["G1_shift"]["metrics"]] == ["alternative_lead_time"]
    assert imp["G1_shift"]["messages"][0]["id"] == "C1" and imp["G1_shift"]["effective_at"]

    packet = inc["packet"]
    assert next(c for c in packet["comms"] if c["id"] == "C1")["required_by_option_ids"] == ["G1_shift"]


def test_the_decision_request_jev_receives_is_compiled_from_the_packet(app_client, stub, jev, live):
    stub.load(agents())
    jev.load(lambda body: f.jev_body(body))
    post_event(app_client)
    decision = jev.calls[-1]["body"]
    assert set(decision["questions"]) == {"group__G1", "action__A_notify", "action__A_reserve", "priority"}
    assert decision["questions"]["group__G1"]["type"] == "choice"
    assert list(decision["questions"]["group__G1"]["criteria"]) == ["G1_shift", "G1_wait"]
    assert "SUP-0001 supplies 60% of PRT-0001" in decision["state"]
    assert "How experienced operators handled similar events" in decision["state"]  # a supplier fire precedent


def test_the_llm_agents_never_see_a_probability_or_a_verdict(app_client, stub, jev, live):
    stub.load(agents())
    jev.load(lambda body: f.jev_body(body))
    post_event(app_client)
    for call in stub.calls:
        text = str(call["messages"])
        assert "auto_approved" not in text and "probabilities" not in text


def test_not_critical_waits_for_a_person(app_client, stub, jev, live):
    stub.load(agents())
    jev.load(lambda body: f.jev_body(body, priority="high", p_priority=0.7, noul=0.9))
    d = post_event(app_client).json()
    assert d["incident"]["status"] == "awaiting_approval" and d["incident"]["auto"] is False
    assert {o["status"] for o in options(d).values()} == {"pending"}
    assert d["approvals"] == [] and d["impact"] == []


# --------------------------------------------------------------------------- people act

def test_approving_one_exclusive_option_deselects_its_siblings(app_client, stub, jev, live):
    stub.load(agents())
    jev.load(lambda body: f.jev_body(body, priority="medium", p_priority=0.6))
    iid = post_event(app_client).json()["incident"]["id"]
    base = f"/api/incidents/{iid}/options"
    d = app_client.post(f"{base}/G1_wait/approve", json={"note": "assessment due tonight"}).json()
    o = options(d)
    assert o["G1_wait"]["status"] == "approved" and o["G1_shift"]["status"] == "not_selected"
    assert d["incident"]["status"] == "awaiting_approval"  # the independent actions are still open
    app_client.post(f"{base}/A_notify/approve")
    d = app_client.post(f"{base}/A_reserve/reject", json={"note": "not needed yet"}).json()
    assert options(d)["A_reserve"]["status"] == "rejected"
    assert d["incident"]["status"] == "resolved"
    assert [(a["option_id"], a["action"], a["actor"]) for a in d["approvals"]] == [
        ("G1_wait", "approve", "user"), ("A_notify", "approve", "user"), ("A_reserve", "reject", "user")]


def test_a_person_can_override_an_auto_approval(app_client, stub, jev, live):
    stub.load(agents())
    jev.load(lambda body: f.jev_body(body, priority="critical"))
    iid = post_event(app_client).json()["incident"]["id"]
    d = app_client.post(f"/api/incidents/{iid}/options/G1_wait/approve").json()
    o = options(d)
    assert o["G1_shift"]["status"] == "superseded" and o["G1_wait"]["status"] == "approved"
    d = app_client.post(f"/api/incidents/{iid}/options/A_notify/reject").json()
    assert options(d)["A_notify"]["status"] == "rejected"
    assert "A_notify" not in {i["option_id"] for i in d["impact"]}


def test_unknown_incidents_and_options_are_404(app_client, stub, jev, live):
    stub.load(agents())
    jev.load(lambda body: f.jev_body(body))
    iid = post_event(app_client).json()["incident"]["id"]
    assert app_client.get("/api/incidents/INC-NOPE").status_code == 404
    assert app_client.post(f"/api/incidents/{iid}/options/NOPE/approve").status_code == 404


# --------------------------------------------------------------------------- the loop and the repairs

def test_the_loop_runs_until_jev_says_enough_or_the_cap(app_client, stub, jev, live, settings_env):
    settings_env(RIPPLE_INCIDENT_MAX_ROUNDS=2)
    stub.load(agents(turns=[ASK]))  # the orchestrator always has another question
    jev.load(lambda body: f.jev_body(body, noul={"sufficient": 0.1, "expert__sourcing_risk": 0.9}))
    d = post_event(app_client).json()
    assert [x["round"] for x in d["incident"]["exchanges"]] == [1, 2]
    assert [j["purpose"] for j in d["jev"]] == ["relevance", "sufficiency", "sufficiency", "decision"]


def test_the_loop_stops_when_the_orchestrator_has_nothing_to_ask(app_client, stub, jev, live):
    stub.load(agents(turns=[ASK, {"asks": []}]))
    jev.load(lambda body: f.jev_body(body, noul={"sufficient": 0.1, "expert__sourcing_risk": 0.9}))
    d = post_event(app_client).json()
    assert len(d["incident"]["exchanges"]) == 1 and d["incident"]["status"] != "failed"


def test_no_relevant_expert_still_consults_jevs_best(app_client, stub, jev, live):
    stub.load(agents())
    jev.load(lambda body: f.jev_body(body, noul=0.2))
    d = post_event(app_client).json()
    assert d["incident"]["relevant"][0]["consulted"] is True


def test_an_orchestrator_question_to_an_unknown_expert_is_repaired(app_client, stub, jev, live):
    ghost = {"asks": [{"expert": "ghost", "question": "Anything?"}]}
    stub.load(agents(turns=[ghost, ASK, {"asks": []}]))
    jev.load(lambda body: f.jev_body(body))
    d = post_event(app_client).json()
    assert d["incident"]["status"] == "auto_approved"
    assert any("not one of the experts you may ask" in str(c["messages"]) for c in stub.calls)


def test_a_plan_without_a_wait_option_is_repaired(app_client, stub, jev, live):
    bad = f.plan()
    shift = bad["decision_groups"][0]["options"][0]
    bad["decision_groups"][0]["options"] = [shift, {**shift, "id": "G1_other", "title": "Something else"}]
    stub.load(agents(plans=[bad, f.plan()]))
    jev.load(lambda body: f.jev_body(body))
    d = post_event(app_client).json()
    assert d["incident"]["status"] == "auto_approved"
    assert any("exactly one wait/hold option" in str(c["messages"]) for c in stub.calls)


# --------------------------------------------------------------------------- failures are recorded

def test_no_approved_expert_fails_with_a_reason(app_client, stub, jev, scope):
    store.save_expert(scope, f.role(status="draft"))
    d = post_event(app_client).json()
    assert d["incident"]["status"] == "failed" and "no approved expert roles" in d["incident"]["error"]


def test_no_jev_key_fails_with_a_reason(app_client, stub, live):
    set_jev_client(None)
    stub.load(agents())
    d = post_event(app_client).json()
    assert d["incident"]["status"] == "failed" and "no Jev key" in d["incident"]["error"]


def test_jev_http_errors_fail_the_incident(app_client, stub, jev, live):
    stub.load(agents())
    jev.load((503, {"error": "overloaded"}))
    d = post_event(app_client).json()
    assert d["incident"]["status"] == "failed" and "HTTP 503" in d["incident"]["error"]


# --------------------------------------------------------------------------- the webhook

def test_the_webhook_needs_text_and_a_known_tenant(app_client, stub, jev, live):
    assert post_event(app_client, {"kind": "fire"}).status_code == 400
    r = app_client.post("/api/events/nosuchtenant", json=f.event())
    assert r.status_code == 404


def test_the_webhook_secret(app_client, stub, jev, live):
    app_client.app.state.settings = app_client.app.state.settings.model_copy(
        update={"ripple_webhook_secret": "s3cret"})
    stub.load(agents())
    jev.load(lambda body: f.jev_body(body))
    assert post_event(app_client).status_code == 401
    r = app_client.post(f"/api/events/{app_client.tenant_id}", json=f.event(), params={"wait": "true"},
                        headers={"X-Ripple-Webhook-Secret": "s3cret"})
    assert r.status_code == 200


def test_other_text_fields_and_the_raw_body_are_kept(app_client, stub, jev, live):
    stub.load(agents())
    jev.load(lambda body: f.jev_body(body))
    d = post_event(app_client, {"type": "port_closure", "message": "Port of Rotterdam closed by storm",
                                "feed_id": 42}).json()
    inc = d["incident"]
    assert inc["kind"] == "port_closure" and inc["summary"] == "Port of Rotterdam closed by storm"
    assert inc["raw"]["feed_id"] == 42 and inc["received_at"]


def test_without_wait_the_run_happens_in_the_background(app_client, stub, jev, live):
    stub.load(agents())
    jev.load(lambda body: f.jev_body(body))
    r = app_client.post(f"/api/events/{app_client.tenant_id}", json=f.event())
    assert r.status_code == 202
    iid = r.json()["incident_id"]
    deadline = time.time() + 30
    status = ""
    while time.time() < deadline:
        status = app_client.get(f"/api/incidents/{iid}").json()["incident"]["status"]
        if status in ("auto_approved", "awaiting_approval", "failed"):
            break
        time.sleep(0.05)
    assert status == "auto_approved"


def test_list_rerun_and_the_step_trail(app_client, stub, jev, live):
    stub.load(agents())
    jev.load(lambda body: f.jev_body(body))
    iid = post_event(app_client).json()["incident"]["id"]
    again = app_client.post(f"/api/incidents/{iid}/rerun", params={"wait": "true"}).json()
    assert again["incident"]["id"] != iid and again["incident"]["summary"] == f.event()["summary"]
    listed = app_client.get("/api/incidents").json()["incidents"]
    assert {i["id"] for i in listed} == {iid, again["incident"]["id"]}
    steps = app_client.get("/api/onboarding/steps", params={"stage": "incident"}).json()["steps"]
    agents_seen = {s["agent"] for s in steps}
    assert {"webhook", "pipeline", "orchestrator", "sourcing_risk", "analyst", "comms", "planner", "jev"} <= agents_seen


def test_the_ui_can_report_an_event_for_the_current_tenant(app_client, stub, jev, live):
    stub.load(agents())
    jev.load(lambda body: f.jev_body(body))
    r = app_client.post("/api/incidents", json=f.event(), params={"wait": "true"})
    assert r.status_code == 200 and r.json()["incident"]["status"] == "auto_approved"


# --------------------------------------------------------------------------- the store

def test_store_round_trips_artifacts_options_and_links(live):
    inc = istore.create_incident(live, EventRecord(summary="Fire at SUP-0001", kind="supplier_site_fire"))
    iid = inc["id"]
    istore.set_incident(live, iid, report=f.report(), status="analysing")
    got = istore.get_incident(live, iid)
    assert got["status"] == "analysing" and got["report"]["evidence"][0]["id"] == "E1" and got["packet"] is None
    istore.save_option(live, iid, option={"id": "X", "title": "Do X"}, group_id="G1", mode="exclusive",
                       probability=0.4, rank=2, status="pending", reason="")
    istore.set_option(live, iid, "X", status="approved")
    assert istore.list_options(live, iid)[0]["status"] == "approved"
    assert istore.link_concerns(live, iid, ["SUP-0001", "SUP-0002", "NOPE-1"]) == 2
    assert [n["id"] for n in istore.nodes_by_ids(live, ["SUP-0001", "NOPE-1"])] == ["SUP-0001"]


# --------------------------------------------------------------------------- validators

def test_orchestrator_turn_validation():
    turn = OrchestratorTurn(asks=[{"expert": "ghost", "question": " "}, {"expert": "a", "question": "q"},
                                  {"expert": "a", "question": "Q"}])
    errs = " | ".join(validate.orchestrator_turn(turn, {"a"}, max_asks=2))
    for needle in ("at most 2", "not one of the experts", "an empty question", "the same question twice"):
        assert needle in errs


def test_evidence_report_validation():
    r = EvidenceReport.model_validate(f.report())
    assert validate.evidence_report(r, {"sourcing_risk"}, {"SUP-0001", "SUP-0002"}) == []
    errs = " | ".join(validate.evidence_report(r, {"other"}, {"SUP-0001"}))
    assert "not an expert that was consulted" in errs and "did not come back" in errs
    assert validate.evidence_report(EvidenceReport(situation="x"), set(), set()) == [
        "no evidence: every claim the experts made that matters to the response must be listed"]


def test_analyst_and_comms_validation():
    rep = EvidenceReport.model_validate(f.report())
    assert validate.analyst_report(AnalystReport.model_validate(f.analysis()), rep) == []
    bad = AnalystReport.model_validate(f.analysis(metrics=[{"name": "x", "value": 1, "basis_evidence_ids": []},
                                                           {"name": "y", "value": 1, "basis_evidence_ids": ["E9"]}],
                                                  affected_node_ids=["GHOST-1"]))
    errs = " | ".join(validate.analyst_report(bad, rep))
    assert "no basis" in errs and "E9" in errs and "GHOST-1" in errs
    assert validate.comms_report(CommsReport.model_validate(f.comms()), rep) == []
    c = f.comms()
    c["drafts"][1].update(id="C1", recipient_node_id="GHOST-1")
    errs = " | ".join(validate.comms_report(CommsReport.model_validate(c), rep))
    assert "duplicate draft ids" in errs and "GHOST-1" in errs


def test_plan_validation():
    groups = [DecisionGroup.model_validate(g) for g in f.plan()["decision_groups"]]
    assert validate.plan(groups, {"E1", "E2"}, {"C1", "C2"}) == []
    p = f.plan()
    p["decision_groups"][1]["options"].append({"id": "G1_shift", "title": "dupe", "action_kind": "x",
                                               "evidence_ids": ["E7"], "comms_ids": ["C9"], "is_wait": True,
                                               "alternative_to": "NOPE"})
    groups = [DecisionGroup.model_validate(g) for g in p["decision_groups"]]
    errs = " | ".join(validate.plan(groups, {"E1", "E2"}, {"C1", "C2"}))
    for needle in ("unique across all groups", "'wait' is not an independent action", "E7", "C9",
                   "alternative_to must name"):
        assert needle in errs
