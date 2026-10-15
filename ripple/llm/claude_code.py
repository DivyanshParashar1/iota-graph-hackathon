"""Claude Code as the LLM provider: no API key, it runs on the local `claude` CLI login (headless `claude -p`).

Each call is one stateless `claude -p` with Claude Code's own tools and MCP servers off: the transcript and the
Ripple tool specs go into the prompt, and the reply comes back as structured output. Two shapes:

* `schema=` given, no tools -> that schema is passed straight to `--json-schema`, so the model's own structured
  output is the agent's parsed result (this is how all four onboarding agents run);
* `tools=` given -> the schema is the step protocol `{text, tool_calls}` and the host runs the tools.

Where `claude` is not installed (the Docker API container) the call goes to the host-side bridge
(`python -m ripple.claude_code_bridge`) at CLAUDE_CODE_BRIDGE_URL instead.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from typing import Any

from ripple.llm.base import LLMError, Reply, ToolCall, log_call

PROTOCOL = """You are the reasoning step of a tool-using agent. You cannot run tools yourself: request them and the
host runs them and shows you the results in the transcript. Each reply is one step:
- to call tools, list them in tool_calls (several are allowed when independent); `text` may be empty;
- when you are done, give the final answer in `text` with tool_calls empty.
Tool inputs must match the tool's JSON schema. Never claim a tool result you have not seen in the transcript."""


def _get(b: Any, k: str, default=None):
    return b.get(k, default) if isinstance(b, dict) else getattr(b, k, default)


def render_transcript(messages: list[dict]) -> str:
    """The conversation as text, since each `claude -p` call is stateless."""
    out = []
    for m in messages:
        content = m["content"]
        if isinstance(content, str):
            out.append(f"### {m['role']}\n{content}")
            continue
        parts = []
        for b in content:
            t = _get(b, "type")
            if t == "text" and _get(b, "text"):
                parts.append(_get(b, "text"))
            elif t == "tool_use":
                parts.append(f"[tool_call id={_get(b, 'id')}] {_get(b, 'name')} {json.dumps(_get(b, 'input') or {})}")
            elif t == "tool_result":
                body = _get(b, "content", "")
                if not isinstance(body, str):
                    body = json.dumps(body, default=str)
                tag = "tool_error" if _get(b, "is_error") else "tool_result"
                parts.append(f"[{tag} id={_get(b, 'tool_use_id')}]\n{body}")
        out.append(f"### {m['role']}\n" + "\n".join(parts))
    return "\n\n".join(out) + "\n\n### your next step"


def tool_protocol_schema(tools: list[dict]) -> dict:
    return {"type": "object", "required": ["text", "tool_calls"], "additionalProperties": False, "properties": {
        "text": {"type": "string"},
        "tool_calls": {"type": "array", "items": {
            "type": "object", "required": ["name", "input"], "additionalProperties": False, "properties": {
                "name": {"type": "string", "enum": [t["name"] for t in tools]},
                "input": {"type": "object"}}}}}}


def build_request(system: str, messages: list[dict], tools: list[dict] | None, schema: dict | None) -> dict:
    """-> {system, prompt, schema} for one `claude -p` call."""
    if tools:
        specs = "\n".join(f"- {t['name']}: {t.get('description', '')}\n  input schema: "
                          f"{json.dumps(t.get('input_schema') or t.get('schema') or {})}" for t in tools)
        system = f"{system}\n\n{PROTOCOL}\n\nTools:\n{specs}"
        out_schema = tool_protocol_schema(tools)
    elif schema:
        out_schema = schema
    else:
        out_schema = {"type": "object", "required": ["text"], "additionalProperties": False,
                      "properties": {"text": {"type": "string"}}}
    return {"system": system, "prompt": render_transcript(messages), "schema": out_schema}


def run_claude(system: str, prompt: str, schema: dict, model: str, effort: str | None = None,
               binary: str = "claude", timeout: float = 600) -> dict:
    """One headless Claude Code call with its built-in tools and MCP servers off. Returns structured output."""
    cmd = [binary, "-p", "--output-format", "json", "--tools", "", "--strict-mcp-config", "--no-session-persistence",
           "--model", model, "--system-prompt", system, "--json-schema", json.dumps(schema)]
    if effort:
        cmd += ["--effort", effort]
    env = {k: v for k, v in os.environ.items()
           if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}  # use the CLI's own login
    try:
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout, env=env,
                           cwd=tempfile.gettempdir())  # outside the repo: no project CLAUDE.md or settings
    except FileNotFoundError:
        raise LLMError(f"{binary!r} is not installed; set CLAUDE_CODE_BRIDGE_URL or another provider") from None
    except subprocess.TimeoutExpired:
        raise LLMError(f"claude timed out after {timeout}s") from None
    try:
        data = json.loads(p.stdout)
    except json.JSONDecodeError:
        raise LLMError(f"claude exited {p.returncode}: {(p.stderr or p.stdout)[-600:]}") from None
    if data.get("is_error") or data.get("subtype") != "success":
        raise LLMError(f"claude error: {data.get('result') or data.get('subtype')}")
    out = data.get("structured_output")
    if out is None:
        try:
            out = json.loads(data.get("result") or "{}")
        except json.JSONDecodeError:
            raise LLMError(f"claude returned no structured output: {(data.get('result') or '')[:400]}") from None
    return {"output": out, "usage": data.get("usage") or {}, "cost_usd": data.get("total_cost_usd")}


class ClaudeCodeClient:
    """`complete(...)` answered by Claude Code (local CLI, or the host bridge from inside Docker)."""

    name = "claude_code"

    def __init__(self, model: str = "opus", binary: str = "claude", bridge_url: str | None = None,
                 bridge_token: str | None = None, timeout: float = 600, http=None):
        self.model = model
        self.binary = binary
        self.bridge_url = bridge_url.rstrip("/") if bridge_url else None
        self.bridge_token = bridge_token
        self.timeout = timeout
        self._http = http
        self._n = 0

    def _run(self, req: dict) -> dict:
        if not self.bridge_url:
            return run_claude(req["system"], req["prompt"], req["schema"], req["model"], req.get("effort"),
                              binary=self.binary, timeout=self.timeout)
        import httpx

        http = self._http or httpx
        headers = {"Authorization": f"Bearer {self.bridge_token}"} if self.bridge_token else {}
        try:
            r = http.post(f"{self.bridge_url}/run", json=req, headers=headers, timeout=self.timeout + 30)
        except Exception as e:  # noqa: BLE001 - the bridge is on the host and may be down
            raise LLMError(f"claude code bridge unreachable: {e}") from None
        if r.status_code != 200:
            raise LLMError(f"claude code bridge {r.status_code}: {r.text[:500]}")
        return r.json()

    def complete(self, *, system: str = "", messages: list[dict], tools: list[dict] | None = None,
                 schema: dict | None = None, max_tokens: int | None = None, effort: str | None = None) -> Reply:
        req = {**build_request(system, messages, tools, schema), "model": self.model, "effort": effort}
        t0 = time.perf_counter()
        res = self._run(req)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        out = res.get("output") if "output" in res else res  # a bridge may return the output alone
        log_call(self.name, req, res, ms)
        reply = Reply(model=self.model, usage=res.get("usage") or {}, ms=ms)
        if tools:
            reply.text = out.get("text") or ""
            for c in out.get("tool_calls") or []:
                self._n += 1
                reply.tool_calls.append(ToolCall(f"cc_{self._n:04d}", c["name"], c.get("input") or {}))
            reply.stop_reason = "tool_use" if reply.tool_calls else "end_turn"
        elif schema:
            reply.data = out
            reply.text = out.get("reply") or out.get("text") or ""
        else:
            reply.text = out.get("text") or ""
        return reply
