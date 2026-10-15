import json
import sys
import threading
from http.server import ThreadingHTTPServer

import pytest

from ripple.agents.claude_code import ClaudeCodeClient, build_request
from ripple.agents.llm import run_llm_agent
from ripple.agents.runtime import AgentRun
from ripple.claude_code_bridge import Handler
from ripple.config import Settings
from ripple.db import TenantScope

FAKE = """#!{py}
import json, os, sys, pathlib
d = pathlib.Path({d!r})
args = sys.argv[1:]
n = len(list(d.glob("call_*.json")))
(d / f"call_{{n}}.json").write_text(json.dumps({{"args": args, "stdin": sys.stdin.read(),
                                                     "api_key": "ANTHROPIC_API_KEY" in os.environ}}))
replies = json.loads((d / "replies.json").read_text())
out = replies[n] if n < len(replies) else {{"text": "Done.", "tool_calls": []}}
if out == "ERROR":
    print(json.dumps({{"type": "result", "subtype": "error_during_execution", "is_error": True, "result": "boom"}}))
else:
    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "structured_output": out}}))
"""


@pytest.fixture
def fake_claude(tmp_path):
    """A stand-in `claude` binary: records each call and answers from replies.json."""
    exe = tmp_path / "claude"
    exe.write_text(FAKE.format(py=sys.executable, d=str(tmp_path)))
    exe.chmod(0o755)

    def set_replies(replies):
        (tmp_path / "replies.json").write_text(json.dumps(replies))

    def calls():
        return [json.loads((tmp_path / f"call_{i}.json").read_text())
                for i in range(len(list(tmp_path.glob("call_*.json"))))]
    set_replies([])
    return SimpleFake(str(exe), set_replies, calls)


class SimpleFake:
    def __init__(self, exe, set_replies, calls):
        self.exe, self.set_replies, self.calls = exe, set_replies, calls


@pytest.fixture(scope="module")
def scope(fresh_db):
    return TenantScope("dataco", fresh_db)


TOOLS = [{"name": "blast_radius", "description": "d", "input_schema": {"type": "object", "properties": {}}}]


def test_build_request_renders_tools_and_transcript():
    req = build_request(system="sys", tools=TOOLS, messages=[
        {"role": "user", "content": "go"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "cc_1", "name": "blast_radius", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "cc_1", "content": "{\"n\": 3}"},
                                     {"type": "tool_result", "tool_use_id": "cc_2", "is_error": True, "content": "x"}]}])
    assert req["system"].startswith("sys") and "blast_radius: d" in req["system"]
    assert req["schema"]["properties"]["tool_calls"]["items"]["properties"]["name"]["enum"] == ["blast_radius"]
    assert "[tool_call id=cc_1] blast_radius {}" in req["prompt"]
    assert "[tool_result id=cc_1]\n{\"n\": 3}" in req["prompt"] and "[tool_error id=cc_2]" in req["prompt"]
    assert build_request(system="s", messages=[{"role": "user", "content": "q"}])["schema"]["required"] == ["text"]


def test_cli_call_and_response(fake_claude, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-not-leak")
    fake_claude.set_replies([{"text": "", "tool_calls": [{"name": "blast_radius", "input": {"k": 1}}]}])
    r = ClaudeCodeClient("opus", fake_claude.exe).messages.create(
        system="sys", tools=TOOLS, output_config={"effort": "medium"}, messages=[{"role": "user", "content": "go"}])
    assert r.stop_reason == "tool_use" and r.content[0].name == "blast_radius" and r.content[0].input == {"k": 1}
    args = fake_claude.calls()[0]["args"]
    assert args[:2] == ["-p", "--output-format"] and args[args.index("--tools") + 1] == ""
    assert args[args.index("--model") + 1] == "opus" and args[args.index("--effort") + 1] == "medium"
    assert "--strict-mcp-config" in args and "### your next step" in fake_claude.calls()[0]["stdin"]
    assert fake_claude.calls()[0]["api_key"] is False  # runs on the Claude Code login, never an API key


def test_agent_loop_runs_on_claude_code(scope, fake_claude):
    fake_claude.set_replies([{"text": "", "tool_calls": [{"name": "single_points_of_failure", "input": {}}]},
                             {"text": "Reviewed.", "tool_calls": []}])
    c = ClaudeCodeClient("opus", fake_claude.exe)
    r = run_llm_agent(AgentRun(scope, "INC-NOPE", "llm"), "analyst", "role", "task", ["single_points_of_failure"],
                      client=c)
    assert r["ok"] and r["text"] == "Reviewed." and r["turns"] == 2
    assert "[tool_result id=cc_0001]" in fake_claude.calls()[1]["stdin"]


def test_cli_error_falls_back(scope, fake_claude):
    fake_claude.set_replies(["ERROR"])
    r = run_llm_agent(AgentRun(scope, "INC-NOPE", "llm"), "analyst", "role", "task", ["single_points_of_failure"],
                      client=ClaudeCodeClient("opus", fake_claude.exe))
    assert not r["ok"] and "boom" in r["reason"]


def test_bridge(fake_claude):
    Handler.binary, Handler.token = fake_claude.exe, "tok"
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        fake_claude.set_replies([{"text": "hi", "tool_calls": []}])
        r = ClaudeCodeClient("sonnet", bridge_url=url, bridge_token="tok").messages.create(
            system="s", tools=TOOLS, messages=[{"role": "user", "content": "q"}])
        assert r.stop_reason == "end_turn" and r.content[0].text == "hi"
        args = fake_claude.calls()[0]["args"]
        assert args[args.index("--model") + 1] == "sonnet"
        with pytest.raises(RuntimeError, match="401"):
            ClaudeCodeClient(bridge_url=url, bridge_token="wrong").messages.create(messages=[{"role": "user", "content": "q"}])
    finally:
        srv.shutdown()
        Handler.token = None


def test_provider_selection(fake_claude):
    assert Settings(_env_file=None, ripple_llm_provider="claude_code", claude_code_bin=fake_claude.exe).llm_provider == "claude_code"
    assert Settings(_env_file=None, ripple_llm_provider="claude_code", claude_code_bin="/nope/claude").llm_provider is None
    assert Settings(_env_file=None, ripple_llm_provider="claude_code", claude_code_bin="/nope/claude",
                    claude_code_bridge_url="http://host.docker.internal:8765").has_llm
