"""Claude Code as the LLM: no API key, it runs on the local `claude` CLI login (headless `claude -p`).

ClaudeCodeClient has the Anthropic `messages.create` surface, so the tool loop in llm.py runs unchanged and every
tool call still goes through AgentRun.call (logging, SSE, ID validator). Each turn is one stateless
`claude -p` call with Claude Code's own tools disabled: the transcript and the Ripple tool specs go in the
prompt, and the reply comes back as structured output ({text, tool_calls}) that is turned into text and
tool_use blocks.

Where `claude` is not installed (the Docker API container) the call goes to the host-side bridge
(`python -m ripple.claude_code_bridge`) at CLAUDE_CODE_BRIDGE_URL instead.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from types import SimpleNamespace
from typing import Any

PROTOCOL = """You are the reasoning step of a tool-using agent. You cannot run tools yourself: request them and the
host runs them and shows you the results in the transcript. Each reply is one step:
- to call tools, list them in tool_calls (several are allowed when independent); `text` may be empty;
- when you are done, give the final answer in `text` with tool_calls empty.
Tool inputs must match the tool's JSON schema. Never claim a tool result you have not seen in the transcript."""


def _get(b: Any, k: str, default=None):
    return b.get(k, default) if isinstance(b, dict) else getattr(b, k, default)


def render_transcript(messages: list[dict]) -> str:
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


def build_request(**kw) -> dict:
    """Anthropic-style kwargs -> {system, prompt, schema} for one `claude -p` call."""
    tools = kw.get("tools") or []
    system = kw.get("system") or ""
    if tools:
        specs = "\n".join(f"- {t['name']}: {t['description']}\n  input schema: {json.dumps(t['input_schema'])}"
                          for t in tools)
        system = f"{system}\n\n{PROTOCOL}\n\nTools:\n{specs}"
        schema = {"type": "object", "required": ["text", "tool_calls"], "properties": {
            "text": {"type": "string"},
            "tool_calls": {"type": "array", "items": {"type": "object", "required": ["name", "input"], "properties": {
                "name": {"type": "string", "enum": [t["name"] for t in tools]}, "input": {"type": "object"}}}}}}
    else:
        schema = {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}}
    return {"system": system, "prompt": render_transcript(kw.get("messages", [])), "schema": schema}


def run_claude(system: str, prompt: str, schema: dict, model: str, effort: str | None = None,
               binary: str = "claude", timeout: float = 300) -> dict:
    """One headless Claude Code call with its built-in tools and MCP servers off. Returns the structured output."""
    cmd = [binary, "-p", "--output-format", "json", "--tools", "", "--strict-mcp-config", "--no-session-persistence",
           "--model", model, "--system-prompt", system, "--json-schema", json.dumps(schema)]
    if effort:
        cmd += ["--effort", effort]
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}  # use the login
    p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout, env=env,
                       cwd=tempfile.gettempdir())  # outside the repo: no project CLAUDE.md or settings
    try:
        data = json.loads(p.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"claude exited {p.returncode}: {(p.stderr or p.stdout)[-500:]}") from None
    if data.get("is_error") or data.get("subtype") != "success":
        raise RuntimeError(f"claude error: {data.get('result') or data.get('subtype')}")
    out = data.get("structured_output")
    if out is None:
        out = json.loads(data.get("result") or "{}")
    return out


class ClaudeCodeClient:
    """`client.messages.create(**anthropic_kwargs)` answered by Claude Code (local CLI or the host bridge)."""

    def __init__(self, model: str = "opus", binary: str = "claude", bridge_url: str | None = None,
                 bridge_token: str | None = None, timeout: float = 300, http=None):
        self.model = model
        self.binary = binary
        self.bridge_url = bridge_url.rstrip("/") if bridge_url else None
        self.bridge_token = bridge_token
        self.timeout = timeout
        self.messages = self
        self._http = http
        self._n = 0

    def _run(self, req: dict) -> dict:
        if not self.bridge_url:
            return run_claude(binary=self.binary, timeout=self.timeout, **req)
        import httpx

        http = self._http or httpx
        headers = {"Authorization": f"Bearer {self.bridge_token}"} if self.bridge_token else {}
        r = http.post(f"{self.bridge_url}/run", json=req, headers=headers, timeout=self.timeout + 30)
        if r.status_code != 200:
            raise RuntimeError(f"claude code bridge {r.status_code}: {r.text[:500]}")
        return r.json()

    def create(self, **kw) -> SimpleNamespace:
        effort = (kw.get("output_config") or {}).get("effort")
        out = self._run({**build_request(**kw), "model": self.model, "effort": effort})
        content = []
        if out.get("text"):
            content.append(SimpleNamespace(type="text", text=out["text"]))
        for c in out.get("tool_calls") or []:
            self._n += 1
            content.append(SimpleNamespace(type="tool_use", id=f"cc_{self._n:04d}", name=c["name"],
                                           input=c.get("input") or {}))
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else "end_turn"
        return SimpleNamespace(content=content, stop_reason=stop, model=self.model)
