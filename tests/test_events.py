"""The agent step bus and its SSE endpoint: the live trail the UI shows while an agent is working.

Nothing else in the suite touches this path, and it is the only thing between "the agent is thinking" and a
spinner, so it is worth its own file.
"""

from __future__ import annotations

import asyncio
import json

from ripple.onboarding.events import BUS, EventBus, StepEmitter, slim
from ripple.onboarding.store import list_steps
from tests import factories as f
from tests.test_session import interview_turn


def test_events_are_per_tenant_and_sequential():
    bus = EventBus()
    for i in range(3):
        bus.emit("acme", "interviewer", "llm", stage="interview", summary=f"step {i}")
    bus.emit("other", "interviewer", "llm", summary="not acme's")
    acme = bus.history("acme")
    assert [e["seq"] for e in acme] == [1, 2, 3]
    assert [e["summary"] for e in acme] == ["step 0", "step 1", "step 2"]
    assert [e["summary"] for e in bus.history("other")] == ["not acme's"]
    assert [e["seq"] for e in bus.history("acme", after=2)] == [3]
    assert bus.history("nobody") == []


def test_busy_is_a_counter_not_a_flag():
    bus = EventBus()
    assert not bus.busy("acme")
    bus.enter("acme")
    bus.enter("acme")  # a stage transition runs a turn inside a turn
    bus.leave("acme")
    assert bus.busy("acme"), "still busy: the outer turn has not finished"
    bus.leave("acme")
    assert not bus.busy("acme")
    bus.leave("acme")  # never goes negative
    assert not bus.busy("acme")


def test_history_is_bounded():
    bus = EventBus()
    for i in range(2100):
        bus.emit("acme", "a", "llm", summary=str(i))
    history = bus.history("acme")
    assert len(history) == 2000
    assert history[-1]["summary"] == "2099"  # the newest are kept
    assert history[0]["seq"] == 101  # seq keeps counting past the window


def test_slim_caps_what_reaches_a_browser():
    big = {"rows": list(range(500)), "text": "x" * 5000, "prompt": {"system_prompt": "secret"},
           "nested": {"a": {"b": {"c": {"d": {"e": {"f": {"g": 1}}}}}}}}
    out = slim(big)
    assert len(out["rows"]) == 51 and out["rows"][-1].endswith("more")
    assert len(out["text"]) == 2003
    assert out["prompt"] == {}, "a system prompt is not telemetry"
    assert "..." in json.dumps(out)


def test_emitter_writes_to_both_the_bus_and_the_graph(scope):
    BUS.reset(scope.tenant_id)
    emit = StepEmitter(scope, "interview", "interviewer")
    emit("llm", "thinking", data={"turns": 2}, ms=12.0)
    emit("write", "brief patched")
    events = BUS.history(scope.tenant_id)
    assert [e["kind"] for e in events] == ["llm", "write"]
    assert events[0]["agent"] == "interviewer" and events[0]["stage"] == "interview"
    steps = list_steps(scope, "interview")
    assert [s["kind"] for s in steps] == ["llm", "write"]
    assert steps[0]["payload"] == {"turns": 2} and steps[0]["ms"] == 12.0
    BUS.reset(scope.tenant_id)


async def test_stream_replays_history_then_follows():
    bus = EventBus()
    bus.emit("acme", "a", "llm", summary="before")
    seen = []

    async def consume():
        async for ev in bus.stream("acme", after=0, poll=0.01):
            seen.append(ev["summary"])
            if len(seen) == 3:
                return

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    assert seen == ["before"], "history is replayed before anything new arrives"
    bus.emit("acme", "a", "tool", summary="during")
    bus.emit("acme", "a", "done", summary="after")
    await asyncio.wait_for(task, timeout=2)
    assert seen == ["before", "during", "after"]


def test_the_sse_route_is_wired_to_the_bus(app_client, stub):
    """The endpoint is an unbounded generator, so the stream itself is tested against the bus above
    (`test_stream_replays_history_then_follows`): reading it through TestClient's portal and disconnecting
    mid-stream deadlocks. What is worth asserting here is that the route resolves its tenant the same way the
    rest of the API does, and that a turn really does leave events on that tenant's bus for it to serve."""
    stub.load(interview_turn(brief_patch=f.brief().model_dump()))
    app_client.post("/api/onboarding/start",
                    json={"company": "Acme Shoes", "tenant_id": app_client.tenant_id})
    events = BUS.history(app_client.tenant_id)
    assert [e["kind"] for e in events][:2] == ["llm", "llm"]
    assert events[0]["agent"] == "interviewer" and events[0]["tenant"] == app_client.tenant_id
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    # the persisted trail agrees with the live one, which is what a reconnecting browser rebuilds from
    from ripple.db import TenantScope

    scope = TenantScope(app_client.tenant_id, app_client.app.state.db)
    assert [s["kind"] for s in list_steps(scope)] == [e["kind"] for e in events]
    BUS.reset(app_client.tenant_id)


def test_the_stream_needs_a_known_tenant(app_client):
    """The dependency runs before the generator, so this is an ordinary request, not a stream."""
    assert app_client.get("/api/onboarding/stream?tenant=nope").status_code == 404
    assert app_client.get("/api/onboarding/stream?tenant=Bad%20Id").status_code == 400


def test_a_restarted_server_rebuilds_the_trail_from_the_graph(scope):
    BUS.reset(scope.tenant_id)
    StepEmitter(scope, "interview", "interviewer")("llm", "thinking")
    BUS.reset(scope.tenant_id)  # what a process restart does to the in-memory ring
    BUS.seed(scope.tenant_id, list_steps(scope))
    assert [e["summary"] for e in BUS.history(scope.tenant_id)] == ["thinking"]
    BUS.seed(scope.tenant_id, list_steps(scope))  # a second seed is a no-op: nothing is replayed twice
    assert len(BUS.history(scope.tenant_id)) == 1
    BUS.reset(scope.tenant_id)
