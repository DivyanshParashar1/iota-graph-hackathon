import json

import httpx
import pytest

from ripple.agents.llm import run_llm_agent
from ripple.agents.openrouter import OpenRouterClient
from ripple.agents.runtime import AgentRun
from ripple.config import Settings
from ripple.db import TenantScope
from ripple.embed import OpenAICompatEmbedder


def _client(replies: list[dict], seen: list[dict]) -> OpenRouterClient:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v1/chat/completions" and req.headers["authorization"] == "Bearer k"
        seen.append(json.loads(req.content))
        return httpx.Response(200, json=replies.pop(0))
    return OpenRouterClient("k", "anthropic/claude-opus-5.5", http=httpx.Client(transport=httpx.MockTransport(handler)))


def _reply(content=None, tool_calls=None, finish="stop", reasoning=None):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = [{"id": f"call_{i}", "type": "function",
                              "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a) in enumerate(tool_calls)]
    if reasoning:
        msg["reasoning_details"] = reasoning
    return {"model": "anthropic/claude-opus-5.5", "choices": [{"message": msg, "finish_reason": finish}]}


def test_request_and_response_translation():
    seen: list[dict] = []
    rd = [{"type": "reasoning.text", "text": "think"}]
    c = _client([_reply(tool_calls=[("blast_radius", {"incident_id": "INC-1"})], finish="tool_calls", reasoning=rd),
                 _reply("done")], seen)
    tools = [{"name": "blast_radius", "description": "d", "input_schema": {"type": "object", "properties": {}}}]
    r1 = c.messages.create(model="ignored", max_tokens=100, system="sys", tools=tools, tool_choice={"type": "auto"},
                           thinking={"type": "adaptive"}, output_config={"effort": "medium"},
                           messages=[{"role": "user", "content": "go"}])
    assert r1.stop_reason == "tool_use"
    use = [b for b in r1.content if b.type == "tool_use"][0]
    assert use.name == "blast_radius" and use.input == {"incident_id": "INC-1"}
    body = seen[0]
    assert body["model"] == "anthropic/claude-opus-5.5" and body["reasoning"] == {"effort": "medium"}
    assert body["messages"][0] == {"role": "system", "content": "sys"}
    assert body["tools"][0]["function"]["name"] == "blast_radius" and body["tool_choice"] == "auto"
    # second turn: assistant tool call (with reasoning details) + tool result go back in OpenAI shape
    r2 = c.messages.create(max_tokens=100, system="sys", messages=[
        {"role": "user", "content": "go"}, {"role": "assistant", "content": r1.content},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": use.id, "content": "{}"},
                                     {"type": "tool_result", "tool_use_id": "x", "is_error": True, "content": "bad"}]}])
    assert r2.stop_reason == "end_turn" and r2.content[0].text == "done"
    msgs = seen[1]["messages"]
    assert msgs[2]["tool_calls"][0]["id"] == use.id and msgs[2]["reasoning_details"] == rd
    assert msgs[3] == {"role": "tool", "tool_call_id": use.id, "content": "{}"}
    assert msgs[4]["content"] == "ERROR: bad"


@pytest.fixture(scope="module")
def scope(fresh_db):
    return TenantScope("dataco", fresh_db)


def test_agent_loop_runs_over_openrouter(scope):
    seen: list[dict] = []
    c = _client([_reply(tool_calls=[("single_points_of_failure", {})], finish="tool_calls"), _reply("Reviewed.")], seen)
    r = run_llm_agent(AgentRun(scope, "INC-NOPE", "llm"), "analyst", "role", "task", ["single_points_of_failure"], client=c)
    assert r["ok"] and r["turns"] == 2
    tool_msg = seen[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and not tool_msg["content"].startswith("ERROR")


def test_provider_error_falls_back(scope):
    def boom(req):
        return httpx.Response(502, json={"error": {"message": "upstream"}})
    c = OpenRouterClient("k", "m", http=httpx.Client(transport=httpx.MockTransport(boom)))
    r = run_llm_agent(AgentRun(scope, "INC-NOPE", "llm"), "analyst", "role", "task", ["single_points_of_failure"], client=c)
    assert not r["ok"] and r["reason"].startswith("LLM error")


def test_provider_selection():
    assert Settings(_env_file=None, openrouter_api_key="a", anthropic_api_key="b").llm_provider == "openrouter"
    assert Settings(_env_file=None, anthropic_api_key="b").llm_provider == "anthropic"
    assert Settings(_env_file=None, ripple_llm_provider="anthropic", openrouter_api_key="a").llm_provider is None
    assert Settings(_env_file=None, openrouter_api_key="").has_llm is False


def test_embedder_batches_and_probes_dim(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, json))
        data = [{"index": i, "embedding": [float(i), 1.0, 0.0]} for i in range(len(json["input"]))][::-1]
        return httpx.Response(200, json={"data": data}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", fake_post)
    e = OpenAICompatEmbedder("k", "openai/text-embedding-3-small", "https://openrouter.ai/api/v1", "openrouter")
    assert e.dim == 3
    vecs = e.embed_many([f"t{i}" for i in range(300)])
    assert len(vecs) == 300 and vecs[5][0] == 5.0  # order restored from `index`
    assert [len(j["input"]) for _, j in calls[1:]] == [256, 44]
    assert calls[0][0] == "https://openrouter.ai/api/v1/embeddings" and calls[0][1]["model"] == "openai/text-embedding-3-small"
