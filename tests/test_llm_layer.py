"""The provider layer: client selection, request translation, structured output and the tool loop.

Nothing here calls a model. The providers are exercised against their own request builders and a fake
transport (an `httpx`-shaped object or a captured `subprocess` call) - which tests the translation, not the
model. The agents' judgement is tested live, under `-m llm`.
"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, Field

from ripple.config import Settings
from ripple.llm.base import LLMError, Reply, ToolCall, get_client
from ripple.llm.claude_code import build_request, render_transcript, tool_protocol_schema
from ripple.llm.loop import extract_ids, run_tool_loop
from ripple.llm.openrouter import to_openai_messages
from ripple.llm.structured import ask_model, extract_json, json_schema


class Small(BaseModel):
    reply: str
    n: int = 0
    tags: list[str] = Field(default_factory=list)


TOOLS = [{"name": "find_nodes", "description": "find", "input_schema": {"type": "object", "properties": {}}},
         {"name": "get_node", "description": "get", "input_schema": {"type": "object", "properties": {}}}]


# --------------------------------------------------------------------------- provider selection

def test_provider_selection():
    s = Settings(ripple_llm_provider="claude_code", claude_code_bin="definitely-not-installed")
    assert s.llm_provider is None and not s.has_llm
    s = Settings(ripple_llm_provider="claude_code", claude_code_bridge_url="http://host:8765")
    assert s.llm_provider == "claude_code" and s.model_name == "opus"
    s = Settings(ripple_llm_provider="openrouter", openrouter_api_key="k")
    assert s.llm_provider == "openrouter" and s.model_name == s.openrouter_model
    assert Settings(ripple_llm_provider="openrouter").llm_provider is None
    s = Settings(ripple_llm_provider="anthropic", anthropic_api_key="k")
    assert s.llm_provider == "anthropic" and s.model_name == s.ripple_model
    s = Settings(ripple_llm_provider="auto", claude_code_bin="definitely-not-installed",
                 openrouter_api_key="k", anthropic_api_key="k2")
    assert s.llm_provider == "openrouter"
    s = Settings(ripple_llm_provider="vertex", vertex_access_token="t")
    assert s.llm_provider == "vertex" and s.model_name == s.vertex_model


def test_vertex_sends_messages_to_the_vertex_endpoint():
    import httpx2 as httpx
    from anthropic import AnthropicVertex

    from ripple.llm.vertex import ClaudeVertexClient

    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["authorization"], json.loads(req.content)
        return httpx.Response(200, json={"id": "m", "type": "message", "role": "assistant", "model": "claude-x",
                                         "content": [{"type": "text", "text": "hi"}], "stop_reason": "end_turn",
                                         "usage": {"input_tokens": 1, "output_tokens": 1}})

    sdk = AnthropicVertex(project_id="p", region="us-east5", access_token="tok",
                          http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    reply = ClaudeVertexClient("p", "us-east5", "claude-x", token="tok", client=sdk).complete(
        system="s", messages=[{"role": "user", "content": "hello"}])
    assert reply.text == "hi"
    assert seen["auth"] == "Bearer tok"
    assert seen["url"].endswith("/projects/p/locations/us-east5/publishers/anthropic/models/claude-x:rawPredict")
    assert seen["body"]["anthropic_version"] and "model" not in seen["body"]


def test_gemini_on_vertex_round_trips_thought_signatures_and_retries_malformed_calls():
    import httpx

    from ripple.llm.vertex import GeminiVertexClient

    sig = {"google": {"thought_signature": "sig-1"}}
    replies = [{"choices": [{"finish_reason": "malformed_function_call", "message": {}}]},
               {"choices": [{"finish_reason": "tool_calls", "message": {"content": None, "tool_calls": [
                   {"id": "c1", "type": "function", "extra_content": sig,
                    "function": {"name": "get_stock", "arguments": '{"sku": "A-17"}'}}]}}]},
               {"choices": [{"finish_reason": "stop", "message": {"content": "40 units"}}]}]
    sent = []

    def handler(req: httpx.Request) -> httpx.Response:
        sent.append((str(req.url), req.headers["authorization"], json.loads(req.content)))
        return httpx.Response(200, json=replies[len(sent) - 1])

    c = GeminiVertexClient("p", "global", "gemini-x", token="tok",
                           http=httpx.Client(transport=httpx.MockTransport(handler)))
    tools = [{"name": "get_stock", "input_schema": {"type": "object", "properties": {"sku": {"type": "string"}}}}]
    msgs = [{"role": "user", "content": "stock of A-17?"}]
    r = c.complete(messages=msgs, tools=tools, effort="low")
    assert len(sent) == 2 and r.tool_calls[0].extra == sig  # the malformed reply was resampled
    url, auth, body = sent[0]
    assert url == "https://aiplatform.googleapis.com/v1/projects/p/locations/global/endpoints/openapi/chat/completions"
    assert auth == "Bearer tok" and body["model"] == "google/gemini-x"
    assert body["reasoning_effort"] == "low" and "reasoning" not in body
    msgs += [r.assistant_message(), {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "c1", "content": "40"}]}]
    assert c.complete(messages=msgs, tools=tools).text == "40 units"
    assert sent[2][2]["messages"][1]["tool_calls"][0]["extra_content"] == sig


def test_no_provider_raises_rather_than_falling_back():
    s = Settings(ripple_llm_provider="none")
    with pytest.raises(LLMError) as e:
        get_client(s)
    assert "no LLM provider" in str(e.value)


def test_the_stub_is_installed_process_wide(stub):
    stub.script = [{"reply": "hi", "n": 3}]
    assert get_client() is stub
    out, reply = ask_model(stub, Small, "sys", [{"role": "user", "content": "hello"}])
    assert (out.reply, out.n) == ("hi", 3)
    assert stub.calls[0]["system"] == "sys"
    assert reply.data == {"reply": "hi", "n": 3}


# --------------------------------------------------------------------------- structured output

def test_json_schema_inlines_refs():
    schema = json_schema(Small)
    assert schema["properties"]["tags"]["type"] == "array"
    assert "$defs" not in json.dumps(schema)

    class Outer(BaseModel):
        inner: Small
        many: list[Small] = Field(default_factory=list)

    s = json_schema(Outer)
    assert s["properties"]["inner"]["properties"]["reply"]["type"] == "string"
    assert s["properties"]["many"]["items"]["properties"]["n"]["type"] == "integer"
    assert "$ref" not in json.dumps(s)


@pytest.mark.parametrize("text,expected", [
    ('{"a": 1}', {"a": 1}),
    ('```json\n{"a": 1}\n```', {"a": 1}),
    ('Sure! {"a": 1} hope that helps', {"a": 1}),
    ("not json at all", None),
    ("", None),
    ("[1,2]", None),
])
def test_extract_json(text, expected):
    assert extract_json(text) == expected


def test_structured_output_repairs_once(stub):
    stub.script = [{"n": "not an int"}, {"reply": "fixed", "n": 2}]
    out, _ = ask_model(stub, Small, "sys", [{"role": "user", "content": "go"}])
    assert out.reply == "fixed"
    assert len(stub.calls) == 2
    repair = stub.calls[1]["messages"][-1]["content"]
    assert "did not validate" in repair and "n:" in repair


def test_structured_output_gives_up_after_the_repair(stub):
    stub.script = [{"n": "bad"}, {"n": "still bad"}]
    with pytest.raises(LLMError) as e:
        ask_model(stub, Small, "sys", [{"role": "user", "content": "go"}])
    assert "did not validate after 2 attempts" in str(e.value)
    assert len(stub.calls) == 2


# --------------------------------------------------------------------------- claude code provider

def test_claude_code_request_without_tools_passes_the_schema_through():
    schema = json_schema(Small)
    req = build_request("be brief", [{"role": "user", "content": "hi"}], None, schema)
    assert req["schema"] == schema
    assert req["system"] == "be brief"
    assert req["prompt"].startswith("### user\nhi")
    assert req["prompt"].endswith("### your next step")


def test_claude_code_request_with_tools_uses_the_step_protocol():
    req = build_request("be brief", [{"role": "user", "content": "hi"}], TOOLS, None)
    assert req["schema"] == tool_protocol_schema(TOOLS)
    names = req["schema"]["properties"]["tool_calls"]["items"]["properties"]["name"]["enum"]
    assert names == ["find_nodes", "get_node"]
    assert "find_nodes: find" in req["system"] and "cannot run tools yourself" in req["system"]


def test_claude_code_renders_tool_results_into_the_transcript():
    messages = [
        {"role": "user", "content": "how many suppliers?"},
        {"role": "assistant", "content": [{"type": "text", "text": "looking"},
                                          {"type": "tool_use", "id": "t1", "name": "find_nodes",
                                           "input": {"label": "Supplier"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1",
                                      "content": {"summary": "2 nodes"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t2", "is_error": True,
                                      "content": "boom"}]},
    ]
    text = render_transcript(messages)
    assert "[tool_call id=t1] find_nodes {\"label\": \"Supplier\"}" in text
    assert "[tool_result id=t1]" in text and '"summary": "2 nodes"' in text
    assert "[tool_error id=t2]\nboom" in text


def test_claude_code_client_parses_a_structured_reply(monkeypatch):
    from ripple.llm import claude_code

    captured = {}

    def fake_run(system, prompt, schema, model, effort=None, binary="claude", timeout=600):
        captured.update(system=system, prompt=prompt, schema=schema, model=model, effort=effort)
        return {"output": {"reply": "two", "n": 2}, "usage": {"input_tokens": 10}}

    monkeypatch.setattr(claude_code, "run_claude", fake_run)
    c = claude_code.ClaudeCodeClient("opus")
    reply = c.complete(system="sys", messages=[{"role": "user", "content": "hi"}],
                       schema=json_schema(Small), effort="low")
    assert reply.data == {"reply": "two", "n": 2} and reply.text == "two"
    assert reply.usage == {"input_tokens": 10} and reply.model == "opus"
    assert captured["effort"] == "low" and captured["model"] == "opus"


def test_claude_code_client_parses_tool_calls(monkeypatch):
    from ripple.llm import claude_code

    monkeypatch.setattr(claude_code, "run_claude", lambda *a, **k: {
        "output": {"text": "", "tool_calls": [{"name": "find_nodes", "input": {"label": "Supplier"}}]}})
    c = claude_code.ClaudeCodeClient("opus")
    reply = c.complete(messages=[{"role": "user", "content": "hi"}], tools=TOOLS)
    assert reply.stop_reason == "tool_use"
    assert [(t.name, t.input) for t in reply.tool_calls] == [("find_nodes", {"label": "Supplier"})]
    assert reply.assistant_message()["content"][0]["type"] == "tool_use"


def test_claude_code_bridge_errors_become_llm_errors():
    from ripple.llm.claude_code import ClaudeCodeClient

    class Http:
        @staticmethod
        def post(*a, **k):
            class R:
                status_code = 502
                text = "claude error: not logged in"
            return R()

    c = ClaudeCodeClient("opus", bridge_url="http://host:8765", http=Http())
    with pytest.raises(LLMError) as e:
        c.complete(messages=[{"role": "user", "content": "hi"}])
    assert "not logged in" in str(e.value)


# --------------------------------------------------------------------------- openrouter provider

def test_openrouter_message_translation():
    out = to_openai_messages("sys", [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": [{"type": "text", "text": "ok"},
                                          {"type": "tool_use", "id": "t1", "name": "find_nodes",
                                           "input": {"label": "Supplier"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "2 nodes"}]},
    ])
    assert out[0] == {"role": "system", "content": "sys"}
    assert out[2]["tool_calls"][0]["function"]["name"] == "find_nodes"
    assert out[3] == {"role": "tool", "tool_call_id": "t1", "content": "2 nodes"}


def test_openrouter_payload_shapes():
    from ripple.llm.openrouter import OpenRouterClient

    c = OpenRouterClient("k", "anthropic/claude-opus-5.5")
    body = c.payload("sys", [{"role": "user", "content": "hi"}], None, json_schema(Small), 100, "high")
    assert body["response_format"]["json_schema"]["schema"]["properties"]["reply"]["type"] == "string"
    assert body["reasoning"] == {"effort": "high"} and body["max_tokens"] == 100
    body = c.payload("sys", [{"role": "user", "content": "hi"}], TOOLS, None, None, None)
    assert body["tools"][0]["function"]["name"] == "find_nodes" and body["tool_choice"] == "auto"
    assert "response_format" not in body


def test_openrouter_parses_a_reply():
    from ripple.llm.openrouter import OpenRouterClient

    class Http:
        @staticmethod
        def post(*a, **k):
            class R:
                status_code = 200

                @staticmethod
                def raise_for_status():
                    return None

                @staticmethod
                def json():
                    return {"model": "m", "choices": [{"finish_reason": "tool_calls", "message": {
                        "content": "looking", "tool_calls": [{"id": "c1", "type": "function", "function": {
                            "name": "find_nodes", "arguments": '{"label": "Supplier"}'}}]}}]}
            return R()

    c = OpenRouterClient("k", "m", http=Http())
    reply = c.complete(messages=[{"role": "user", "content": "hi"}], tools=TOOLS)
    assert reply.text == "looking" and reply.stop_reason == "tool_use"
    assert reply.tool_calls[0].input == {"label": "Supplier"}


# --------------------------------------------------------------------------- the tool loop

def test_extract_ids():
    assert extract_ids("SUP-0001 and PRT-0002 but not supplier or X") == {"SUP-0001", "PRT-0002"}
    assert extract_ids("") == set()


def test_tool_loop_runs_tools_then_answers(stub):
    stub.script = [("", [("find_nodes", {"label": "Supplier"})]), "SUP-0001 is the only one."]
    calls = []

    def call(name, args):
        calls.append((name, args))
        return {"summary": "1 node", "node_ids": ["SUP-0001"], "data": {"nodes": [{"id": "SUP-0001"}]}}

    out = run_tool_loop(stub, system="sys", task="who?", tools=TOOLS, call=call)
    assert out["ok"] and out["turns"] == 2 and out["ids"] == ["SUP-0001"]
    assert calls == [("find_nodes", {"label": "Supplier"})]
    kinds = [s["kind"] for s in out["steps"]]
    assert kinds == ["tool_call", "tool_result", "answer"]


def test_tool_loop_rejects_invented_ids_then_accepts_the_rewrite(stub):
    stub.script = [("", [("find_nodes", {})]), "SUP-9999 is late.", "SUP-0001 is late."]

    def call(name, args):
        return {"summary": "1 node", "node_ids": ["SUP-0001"]}

    out = run_tool_loop(stub, system="sys", task="who?", tools=TOOLS, call=call)
    assert out["ok"] and out["text"] == "SUP-0001 is late."
    assert any(s["kind"] == "error" and "validator" in s["summary"] for s in out["steps"])


def test_tool_loop_gives_up_on_a_second_invented_id(stub):
    stub.script = [("", [("find_nodes", {})]), "SUP-9999", "SUP-8888"]
    out = run_tool_loop(stub, system="sys", task="who?", tools=TOOLS,
                        call=lambda n, a: {"summary": "", "node_ids": ["SUP-0001"]})
    assert not out["ok"] and "validator" in out["reason"]


def test_tool_loop_passes_tool_errors_back_to_the_model(stub):
    stub.script = [("", [("find_nodes", {"label": "Ghost"})]), "There is no Ghost type."]

    def call(name, args):
        raise ValueError("unknown type 'Ghost'")

    out = run_tool_loop(stub, system="sys", task="who?", tools=TOOLS, call=call)
    assert out["ok"]
    assert any(s["kind"] == "tool_error" for s in out["steps"])
    results = stub.calls[1]["messages"][-1]["content"]
    assert results[0]["is_error"] and "Ghost" in results[0]["content"]


def test_tool_loop_refuses_a_tool_outside_the_allow_list(stub):
    stub.script = [("", [("delete_everything", {})]), "I cannot do that."]
    out = run_tool_loop(stub, system="sys", task="go", tools=TOOLS, call=lambda n, a: {})
    assert out["ok"]
    results = stub.calls[1]["messages"][-1]["content"]
    assert results[0]["is_error"] and "not available" in results[0]["content"]


def test_tool_loop_stops_at_max_turns(stub):
    stub.script = [("", [("find_nodes", {})])]
    out = run_tool_loop(stub, system="sys", task="go", tools=TOOLS,
                        call=lambda n, a: {"summary": "", "node_ids": []}, max_turns=3)
    assert not out["ok"] and out["reason"] == "max turns" and out["turns"] == 3


def test_tool_loop_reports_a_provider_failure():
    class Broken:
        name = model = "broken"

        def complete(self, **kw):
            raise LLMError("transport exploded")

    out = run_tool_loop(Broken(), system="s", task="t", tools=TOOLS, call=lambda n, a: {})
    assert not out["ok"] and "transport exploded" in out["reason"]


def test_reply_assistant_message_round_trip():
    r = Reply(text="hi", tool_calls=[ToolCall("t1", "find_nodes", {"label": "Supplier"})])
    msg = r.assistant_message()
    assert msg["role"] == "assistant"
    assert [b["type"] for b in msg["content"]] == ["text", "tool_use"]
    assert Reply().assistant_message()["content"] == [{"type": "text", "text": ""}]


# --------------------------------------------------------------------------- schemas the providers accept

def test_every_agent_turn_schema_is_flat_and_finite():
    """A provider rejects a schema with an unresolved or truncated `$ref`, so build every one the agents send.

    This is the deterministic counterpart to a failure that only a real provider found: `FormField.fields` used
    to be `list[FormField]`, and inlining it produced a schema whose innermost `fields` was no longer an array.
    """
    from ripple.onboarding.models import (
        DataTurn,
        ExpertsTurn,
        InstanceBatch,
        InterviewTurn,
        OntologyTurn,
        SynthesizedForm,
    )

    for cls in (InterviewTurn, DataTurn, OntologyTurn, ExpertsTurn, InstanceBatch, SynthesizedForm):
        schema = json_schema(cls)
        body = json.dumps(schema)
        assert "$ref" not in body and "$defs" not in body, cls.__name__
        assert len(body) < 60_000, f"{cls.__name__} schema is {len(body)} chars"
        _assert_well_formed(schema, cls.__name__)


def _assert_well_formed(node, where: str, depth: int = 0) -> None:
    assert depth < 30, f"{where}: schema nests more than 30 deep"
    if isinstance(node, dict):
        if node.get("type") == "array":
            assert "items" in node, f"{where}: an array with no items"
        for k, v in node.items():
            _assert_well_formed(v, f"{where}.{k}", depth + 1)
    elif isinstance(node, list):
        for v in node:
            _assert_well_formed(v, where, depth + 1)


def test_a_recursive_model_is_refused_at_build_time():
    from ripple.llm.structured import RecursiveModel

    class Node(BaseModel):
        name: str
        children: list[Node] = Field(default_factory=list)

    Node.model_rebuild()
    with pytest.raises(RecursiveModel):
        json_schema(Node)
