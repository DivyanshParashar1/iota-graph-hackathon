"""Compiling packets into Jev requests, the auto-approval policy, and the precedent set. All pure: no LLM, no DB.

The packet used throughout is the worked scenario in eval/decisions/scenario_felixstowe_fire.json.
"""

from __future__ import annotations

import pytest

from ripple.decide import policy
from ripple.decide import precedents as prec
from ripple.decide.compile import (
    PRIORITY_LEVELS,
    decision_request,
    qid,
    relevance_request,
    render_state,
    sufficiency_request,
)
from ripple.decide.jev import estimate_tokens, parse_response
from ripple.incident import validate
from ripple.incident.models import DecisionPacket, EventRecord, Exchange
from tests import factories as f


@pytest.fixture
def packet() -> DecisionPacket:
    return DecisionPacket.model_validate(f.scenario()["decision_packet"])


def result(packet, **kw):
    req, qmap = decision_request(packet)
    return parse_response(f.jev_body(req.body("m"), **kw), req), qmap


# --------------------------------------------------------------------------- the scenario itself

def test_the_scenario_packet_is_a_valid_plan(packet):
    eids = {e.id for e in packet.evidence}
    cids = {c.id for c in packet.comms}
    assert validate.plan(packet.decision_groups, eids, cids) == []


# --------------------------------------------------------------------------- compile

def test_each_group_becomes_the_right_question_type(packet):
    req, qmap = decision_request(packet, prec.nearest(packet.event.kind, packet.event.summary))
    assert req.problems() == []
    assert qmap.choice == {"group__G1": "G1"}
    assert set(qmap.noul) == {"action__A_divert_inbound", "action__A_notify_insurer", "action__A_notify_customers"}
    g1 = req.questions["group__G1"]
    assert g1.type == "choice" and list(g1.criteria) == ["G1_a_reblend", "G1_b_spot_buy", "G1_c_allocate", "G1_d_wait"]
    assert "Irreversible" in g1.criteria["G1_b_spot_buy"] and "72h" in g1.criteria["G1_b_spot_buy"]
    assert "Escalate on weak signals" in g1.instructions  # the human heuristics ride on every choice
    assert req.questions["action__A_notify_insurer"].criteria["true"].startswith("Doing this now")
    pr = req.questions["priority"]
    assert pr.type == "score" and pr.level_names() == [n for n, _ in PRIORITY_LEVELS]


def test_the_state_carries_event_evidence_analysis_options_and_precedents(packet):
    near = prec.nearest(packet.event.kind, packet.event.summary)
    state = render_state(packet, near)
    for needle in ("## Event", "external webhook", "E1 (Bonded Warehousing & Customs, fact)", "## Impact analysis",
                   "days_of_cover_house_espresso: 6", "## Drafted messages", "G1_d_wait",
                   "How experienced operators handled similar events"):
        assert needle in state
    assert any(r["id"] in ("ocado-andover-2019",) for r in near)


def test_the_state_is_cut_to_budget_precedents_first(packet):
    near = prec.nearest(packet.event.kind, packet.event.summary)
    full = render_state(packet, near)
    small = render_state(packet, near, budget_tokens=estimate_tokens(full) - 50)
    assert estimate_tokens(small) <= estimate_tokens(full) - 50
    assert "## Evidence" in small and "## Proposed options" in small
    tiny = render_state(packet, near, budget_tokens=300)
    assert estimate_tokens(tiny) <= 300 and tiny.endswith("...(truncated)")


def test_question_ids_are_identifiers_whatever_the_planner_wrote():
    assert qid("action", "A-notify insurer!") == "action__A_notify_insurer_"


def test_relevance_asks_one_noul_per_role():
    roles = [f.role(), f.role(name="logistics", title="Logistics Lead", mandate="Owns lanes.")]
    req, names = relevance_request(EventRecord(summary="Port closed", kind="port_closure"), roles)
    assert req.problems() == []
    assert names == {"expert__sourcing_risk": "sourcing_risk", "expert__logistics": "logistics"}
    assert all(q.type == "noul" for q in req.questions.values())
    assert "Port closed" in req.state


def test_sufficiency_is_one_noul_over_the_transcript():
    ex = [Exchange(round=1, expert="sourcing_risk", question="Who supplies soles?", answer="SUP-0001 and SUP-0002.")]
    req = sufficiency_request(EventRecord(summary="Fire"), ex)
    assert list(req.questions) == ["sufficient"] and "SUP-0001 and SUP-0002" in req.state


# --------------------------------------------------------------------------- policy

T = policy.Thresholds(priority_min=0.5, noul_min=0.6, approve_wait=True)


def test_critical_auto_approves_jevs_choice_and_confident_actions(packet):
    res, qmap = result(packet, priority="critical", p_priority=0.8, choice={"group__G1": "G1_b_spot_buy"},
                       noul={"action__A_divert_inbound": 0.9, "action__A_notify_insurer": 0.7,
                             "action__A_notify_customers": 0.4})
    out = policy.apply(packet, res, qmap, T)
    v = out.by_option()
    assert out.auto and out.priority == "critical"
    assert v["G1_b_spot_buy"].status == "auto_approved" and v["G1_b_spot_buy"].rank == 1
    assert {v[o].status for o in ("G1_a_reblend", "G1_c_allocate", "G1_d_wait")} == {"not_selected"}
    assert v["A_divert_inbound"].status == "auto_approved" and v["A_notify_insurer"].status == "auto_approved"
    assert v["A_notify_customers"].status == "pending"  # under 0.6: a person decides


def test_not_critical_means_a_person_decides_everything(packet):
    res, qmap = result(packet, priority="high", p_priority=0.7, noul=0.95)
    out = policy.apply(packet, res, qmap, T)
    assert not out.auto and out.priority == "high"
    assert {v.status for v in out.verdicts} == {"pending"}
    assert "a human decides" in out.reason


def test_critical_but_unsure_is_not_auto(packet):
    res, qmap = result(packet, priority="critical", p_priority=0.4, noul=0.95)
    out = policy.apply(packet, res, qmap, T)
    assert out.priority == "critical" and not out.auto


def test_a_winning_wait_is_a_hold_only_when_config_allows(packet):
    res, qmap = result(packet, priority="critical", choice={"group__G1": "G1_d_wait"})
    assert policy.apply(packet, res, qmap, T).by_option()["G1_d_wait"].status == "auto_approved"
    no_wait = policy.Thresholds(0.5, 0.6, approve_wait=False)
    assert policy.apply(packet, res, qmap, no_wait).by_option()["G1_d_wait"].status == "pending"


def test_the_same_answers_always_give_the_same_verdicts(packet):
    res, qmap = result(packet)
    assert policy.apply(packet, res, qmap, T).to_dict() == policy.apply(packet, res, qmap, T).to_dict()


# --------------------------------------------------------------------------- precedents

def test_the_precedent_file_is_well_formed():
    recs = prec.load()
    assert len(recs) >= 9 and prec.problems(recs) == []
    assert any(r.get("is_negative_example") for r in recs)


def test_problems_are_reported():
    bad = [{"id": "x", "human_choice": "c", "options_considered": ["a"], "priority_in_hindsight": "urgent",
            "heuristics": ["vibes"]}]
    errs = " | ".join(prec.problems(bad))
    for needle in ("missing event", "not one of options_considered", "fewer than two", "priority_in_hindsight",
                   "unknown heuristics"):
        assert needle in errs


def test_a_warehouse_fire_finds_the_warehouse_fire():
    near = prec.nearest("own_warehouse_fire", "Fire destroyed our fulfilment centre")
    assert near[0]["id"] == "ocado-andover-2019"


def test_a_supplier_fire_keeps_the_nokia_ericsson_pair_together():
    near = prec.nearest("supplier_site_fire", "Fire at a supplier's chip plant", k=3)
    ids = [r["id"] for r in near]
    assert "philips-albuquerque-2000-nokia" in ids and "philips-albuquerque-2000-ericsson" in ids


def test_render_says_which_worked():
    eric = next(r for r in prec.load() if r["id"] == "philips-albuquerque-2000-ericsson")
    assert "This did NOT work." in prec.render(eric)


# --------------------------------------------------------------------------- calibration against precedents

def test_a_precedent_compiles_without_its_outcome_or_choice():
    from ripple.decide.compile import precedent_request

    r = next(x for x in prec.load() if x["id"] == "philips-albuquerque-2000-nokia")
    req, labels = precedent_request(r)
    assert req.problems() == []
    assert list(labels.values()) == r["options_considered"]
    assert r["outcome"] not in req.state and "Chose" not in req.state
    assert req.questions["decision"].criteria == labels


def test_calibration_scores_positive_and_negative_examples():
    from ripple.decide import calibrate
    from tests.conftest import JevTransport

    nokia, eric = (next(x for x in prec.load() if x["id"] == i) for i in
                   ("philips-albuquerque-2000-nokia", "philips-albuquerque-2000-ericsson"))
    escalate = {"decision": "opt_1"}  # both records list "accept and wait" first, "escalate" second
    t = JevTransport([lambda body: f.jev_body(body, choice=escalate, priority="critical")])
    out = calibrate.evaluate(t.client(), (nokia, eric))
    assert out["n"] == 2 and out["errors"] == 0
    assert out["agreement"] == 1.0  # Jev's escalate matches Nokia's choice and differs from Ericsson's
    assert out["priority_agreement"] == 1.0
    assert {r["id"]: r["agrees"] for r in out["rows"]} == {nokia["id"]: True, eric["id"]: True}
