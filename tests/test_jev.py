"""The Jev client: request building, pre-send checks, the HTTP call, and response normalisation.

The response variants below are the shapes third-party guides disagree on. The parser accepts each; once
`scripts/verify_jev.py` has pinned the real one in reference/JEV_VERIFIED.md, the first test here should be
rewritten to that exact body.
"""

from __future__ import annotations

import pytest

from ripple.config import get_settings
from ripple.decide.jev import (
    JevClient,
    JevError,
    JevQuestion,
    JevRequest,
    get_jev_client,
    parse_response,
    set_jev_client,
)
from tests import factories as f
from tests.conftest import JevTransport


def req(**over) -> JevRequest:
    data = {"state": "A fire at the bonded warehouse.", "questions": {
        "group__G1": JevQuestion(type="choice", instructions="Which?", criteria={"a": "Reroute.", "b": "Wait."}),
        "action__A1": JevQuestion(type="noul", instructions="Notify the insurer?",
                                  criteria={"true": "warranted", "false": "not warranted"}),
        "priority": JevQuestion(type="score", instructions="How urgent?",
                                criteria=["low: a week", "medium: days", "high: a day", "critical: hours"])}}
    data.update(over)
    return JevRequest(**data)


# --------------------------------------------------------------------------- the request

def test_body_carries_model_state_and_typed_questions():
    body = req().body("typesafe/jev-1.13")
    assert body["model"] == "typesafe/jev-1.13" and body["state"].startswith("A fire")
    assert body["questions"]["group__G1"] == {"type": "choice", "instructions": "Which?",
                                              "criteria": {"a": "Reroute.", "b": "Wait."}}
    assert body["questions"]["priority"]["criteria"][3] == "critical: hours"


def test_a_valid_request_has_no_problems():
    assert req().problems() == []


def test_problems_catch_what_jev_would_reject():
    bad = req(questions={
        "bad id": JevQuestion(type="noul", instructions="?"),
        "one": JevQuestion(type="choice", instructions="?", criteria={"a": "only one"}),
        "lvl": JevQuestion(type="score", instructions="?", criteria=["only: one"]),
        "nl": JevQuestion(type="noul", instructions="?", criteria={"maybe": "x"})})
    errs = " | ".join(bad.problems())
    assert "not a plain identifier" in errs
    assert "a choice needs 2-255 options" in errs
    assert "a score needs 2-10 levels" in errs
    assert "noul criteria take only" in errs


def test_the_token_budget_is_checked_before_sending():
    big = req(state="x" * (4 * 33_000))
    assert any("longest question" in e for e in big.problems())


def test_score_levels_are_the_text_before_the_colon():
    assert req().questions["priority"].level_names() == ["low", "medium", "high", "critical"]


# --------------------------------------------------------------------------- the response

def test_the_documented_shape_parses():
    body = f.jev_body(req().body("m"), priority="high", p_priority=0.6, choice={"group__G1": "b"}, noul=0.9)
    res = parse_response(body, req())
    g = res["group__G1"]
    assert g.top == "b" and g.p("b") == pytest.approx(0.7) and g.p("a") == pytest.approx(0.3)
    assert res["action__A1"].p_true == pytest.approx(0.9) and res["action__A1"].top == "true"
    assert res["priority"].top == "high" and res["priority"].p("high") == pytest.approx(0.6)
    assert res.model == "typesafe/jev-1.13-20260917"


@pytest.mark.parametrize("noul", [0.83, {"noul": 0.83}, {"probability": 0.83}, {"p": "0.83"},
                                  {"probabilities": {"true": 0.83, "false": 0.17}}, {"noul": True, "confidence": 0.83}])
def test_noul_variants(noul):
    r = JevRequest(state="s", questions={"q": JevQuestion(type="noul", instructions="?")})
    assert parse_response({"answers": {"q": noul}}, r)["q"].p_true == pytest.approx(0.83)


def test_choice_probabilities_as_a_list_of_records_or_aligned_numbers():
    r = req()
    for probs in ([{"label": "a", "probability": 0.2}, {"label": "b", "probability": 0.8}], [0.2, 0.8]):
        body = {"choices": {"group__G1": {"probabilities": probs}, "action__A1": 0.5,
                            "priority": {"score": "critical"}}}
        res = parse_response(body, r)
        assert res["group__G1"].top == "b" and res["group__G1"].p("a") == pytest.approx(0.2)


def test_score_keyed_by_full_criterion_or_index():
    r = req()
    body = {"answers": {"group__G1": {"choice": "a"}, "action__A1": 0.5,
                        "priority": {"probabilities": {"critical: hours": 0.7, "1": 0.3}}}}
    res = parse_response(body, r)
    assert res["priority"].p("critical") == pytest.approx(0.7) and res["priority"].p("medium") == pytest.approx(0.3)
    assert res["priority"].top == "critical"


def test_a_pick_with_only_a_confidence_spreads_the_rest():
    r = req()
    body = {"answers": {"group__G1": {"choice": "a", "confidence": 0.9}, "action__A1": 0.5,
                        "priority": {"score": "low", "confidence": 0.7}}}
    res = parse_response(body, r)
    assert res["group__G1"].p("a") == pytest.approx(0.9) and res["group__G1"].p("b") == pytest.approx(0.1)
    assert res["priority"].p("low") == pytest.approx(0.7) and res["priority"].p("high") == pytest.approx(0.1)


def test_answers_as_a_list_keyed_by_id():
    r = JevRequest(state="s", questions={"q": JevQuestion(type="noul", instructions="?")})
    assert parse_response({"answers": [{"id": "q", "noul": 0.4}]}, r)["q"].p_true == pytest.approx(0.4)


def test_a_missing_answer_or_an_error_body_raises():
    with pytest.raises(JevError, match="no answer for priority"):
        parse_response({"answers": {"group__G1": {"choice": "a"}, "action__A1": 0.5}}, req())
    with pytest.raises(JevError, match="Jev error"):
        parse_response({"error": {"message": "bad key"}}, req())


# --------------------------------------------------------------------------- the client over a transport stub

def test_the_client_posts_to_systemone_with_the_key():
    t = JevTransport([lambda body: f.jev_body(body)])
    res = t.client().decide(req())
    call = t.calls[0]
    assert call["url"] == f"{JevTransport.URL}/systemone"
    assert call["headers"]["authorization"] == "Bearer test-key"
    assert call["body"]["model"] == "typesafe/jev-1.13" and set(call["body"]["questions"]) == set(req().questions)
    assert res["priority"].top == "critical"


def test_http_errors_and_invalid_requests_raise():
    t = JevTransport([(400, {"error": "chat completions does not serve this model"})])
    with pytest.raises(JevError, match="HTTP 400"):
        t.client().decide(req())
    with pytest.raises(JevError, match="refusing to send"):
        t.client().decide(req(questions={}))
    assert len(t.calls) == 1  # the invalid request never left


def test_no_key_is_a_clear_error():
    with pytest.raises(JevError, match="no Jev key"):
        JevClient("", "typesafe/jev-1.13")
    set_jev_client(None)
    with pytest.raises(JevError, match="no Jev key"):
        get_jev_client(get_settings())


def test_the_key_falls_back_to_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert s.jev_key == "or-key" and s.has_jev
        monkeypatch.setenv("JEV_API_KEY", "jev-key")
        get_settings.cache_clear()
        assert get_settings().jev_key == "jev-key"
    finally:  # back to the suite's empty keys (deleting them would let a developer's .env leak in)
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        monkeypatch.setenv("JEV_API_KEY", "")
        get_settings.cache_clear()
