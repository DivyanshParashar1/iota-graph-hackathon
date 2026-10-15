import pytest

from ripple.agents.events import BUS
from ripple.agents.llm import FakeAnthropic, run_llm_agent, set_client
from ripple.agents.orchestrator import Orchestrator, effective_mode, prepare
from ripple.agents.runtime import AgentRun
from ripple.agents import sentinel
from ripple.db import TenantScope
from ripple.scenarios import scenario_event
from ripple.tools.impact import get_incident


@pytest.fixture(scope="module")
def scope(fresh_db):
    return TenantScope("dataco", fresh_db)


def _tu(name, **inp):
    return [{"type": "tool_use", "name": name, "input": inp}]


def test_loop_logs_tools_and_validator_catches_fabricated_id(scope):
    ev = scenario_event("port_congestion_ningbo", "dataco")
    did, iid = prepare(scope, ev)
    fake = FakeAnthropic([
        _tu("match_event_to_entities", event=ev),
        _tu("create_disruption", event=ev, entity_ids=["PORT-CNNGB"]),
        _tu("open_incident", disruption_id=did) + _tu("recall_similar_episodes", incident_id=iid),
        [{"type": "text", "text": f"Opened {iid} for PORT-CNNGB; similar to SUP-T9-9999."}],
        [{"type": "text", "text": f"Opened {iid} for PORT-CNNGB."}],
    ])
    run = AgentRun(scope, iid, "llm")
    r = run_llm_agent(run, "sentinel", sentinel.ROLE, sentinel.task(ev, iid), sentinel.TOOLS, client=fake)
    assert r["ok"] and r["text"].endswith("PORT-CNNGB.")
    assert get_incident(scope, iid) is not None
    # every tool call was logged in the graph with the agent name
    tools = {x["t"] for x in scope.ops.query(
        "MATCH (t:ToolCall {agent: 'sentinel'}) RETURN DISTINCT t.tool AS t")}
    assert {"match_event_to_entities", "create_disruption", "open_incident", "recall_similar_episodes"} <= tools
    # the validator rejected the fabricated id once
    errs = [e for e in BUS.history(iid) if e["kind"] == "error"]
    assert errs and "SUP-T9-9999" in errs[0]["data"]["bad_ids"]
    # API contract of each request
    kw = fake.calls[0]
    assert kw["tool_choice"] == {"type": "auto"} and kw["thinking"] == {"type": "adaptive"}
    assert kw["output_config"] == {"effort": "medium"} and kw["max_tokens"] == 16000
    assert "temperature" not in kw and "budget_tokens" not in str(kw)
    assert {t["name"] for t in kw["tools"]} == set(sentinel.TOOLS)
    # both tool_results of the parallel turn went back in one user message
    third = fake.calls[3]["messages"][-1]
    assert third["role"] == "user" and [c["type"] for c in third["content"]] == ["tool_result", "tool_result"]


def test_validator_fails_twice_falls_back(scope):
    ev = scenario_event("port_congestion_ningbo", "dataco")
    _, iid = prepare(scope, ev)
    fake = FakeAnthropic([[{"type": "text", "text": "See ORD-00000000."}], [{"type": "text", "text": "ORD-11111111."}]])
    r = run_llm_agent(AgentRun(scope, iid, "llm"), "analyst", "x", "y", ["revenue_at_risk"], client=fake)
    assert not r["ok"] and r["reason"].startswith("validator")


def test_tool_errors_are_returned_as_is_error(scope):
    fake = FakeAnthropic([_tu("revenue_at_risk", incident_id="INC-NOPE") + _tu("blast_radius", incident_id="INC-NOPE"),
                          [{"type": "text", "text": "nothing"}]])
    r = run_llm_agent(AgentRun(scope, "INC-NOPE", "llm"), "analyst", "x", "y", ["revenue_at_risk"], client=fake)
    assert r["ok"]
    res = fake.calls[1]["messages"][-1]["content"]
    assert res[1]["is_error"] is True and "not available" in res[1]["content"]


def test_llm_mode_orchestrator_with_fake_falls_back_per_agent(scope):
    fake = FakeAnthropic(default_text="Nothing to add.")
    orch = Orchestrator(scope, "llm", client=fake)
    assert orch.mode == "llm"
    iid = orch.run(scenario_event("carrier_strike", "dataco"))
    evs = BUS.history(iid)
    assert evs[-1]["kind"] == "done" and evs[-1]["data"]["mode"] == "llm"
    assert len(fake.calls) >= 5  # one per agent node
    assert get_incident(scope, iid)["incident"]["summary"]


def test_no_key_downgrades_to_scripted():
    set_client(None)
    assert effective_mode("llm") == ("scripted", "scripted (no API key)")
    assert effective_mode("scripted") == ("scripted", "scripted")


def test_non_fatal_error_does_not_end_the_stream():
    from ripple.agents.events import EventBus
    bus = EventBus()
    bus.emit("INC-X", "comms", "error", summary="who_owns failed", data={"fatal": False})
    assert not bus.is_done("INC-X")
    bus.emit("INC-X", "orchestrator", "error", summary="run failed", data={"fatal": True})
    assert bus.is_done("INC-X")
