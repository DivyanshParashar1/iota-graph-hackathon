"""The provider-agnostic LLM surface every Ripple agent is written against.

One call = `client.complete(system=..., messages=[...], tools=?, schema=?)` -> `Reply`. Messages are
Anthropic-shaped: `{"role": "user"|"assistant", "content": str | [block, ...]}` with blocks
`{"type": "text", "text": ...}`, `{"type": "tool_use", "id", "name", "input"}` and
`{"type": "tool_result", "tool_use_id", "content", "is_error"?}`. Providers translate as needed.

`schema` asks for structured output: the reply's `data` is a dict validated against that JSON schema by the
provider where it can (Claude Code, OpenRouter) and by `ripple.llm.structured` otherwise.

There is no fake provider. Route tests install a tiny transport stub with `set_client` (a stub at the provider
boundary, not a fake agent); everything else that needs a model calls a real one under `-m llm`.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ripple.config import get_settings


class LLMError(RuntimeError):
    """The provider failed (transport, auth, timeout, refusal)."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    input: dict
    # Provider state to send back with this call on the next turn (Gemini's thought signature); usually empty.
    extra: dict = field(default_factory=dict, compare=False)


@dataclass
class Reply:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    data: dict | None = None  # structured output, when a schema was requested
    model: str = ""
    stop_reason: str = "end_turn"
    usage: dict = field(default_factory=dict)
    ms: float = 0.0

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)

    def assistant_message(self) -> dict:
        """This reply as an assistant turn to append to the transcript."""
        blocks: list[dict] = []
        if self.text:
            blocks.append({"type": "text", "text": self.text})
        for c in self.tool_calls:
            block = {"type": "tool_use", "id": c.id, "name": c.name, "input": c.input}
            if c.extra:
                block["extra_content"] = c.extra
            blocks.append(block)
        return {"role": "assistant", "content": blocks or [{"type": "text", "text": ""}]}


@runtime_checkable
class LLMClient(Protocol):
    name: str
    model: str

    def complete(self, *, system: str = "", messages: list[dict], tools: list[dict] | None = None,
                 schema: dict | None = None, max_tokens: int | None = None,
                 effort: str | None = None) -> Reply: ...


_OVERRIDE: Any = None
_LOCK = threading.Lock()


def set_client(client: Any) -> None:
    """Install a client for the whole process (route tests use a transport stub); None restores the default."""
    global _OVERRIDE
    with _LOCK:
        _OVERRIDE = client


def get_client(settings=None) -> LLMClient:
    """The configured provider. Raises LLMError when none is available - v2 never falls back to a script."""
    if _OVERRIDE is not None:
        return _OVERRIDE
    s = settings or get_settings()
    provider = s.llm_provider
    if provider == "claude_code":
        from ripple.llm.claude_code import ClaudeCodeClient

        return ClaudeCodeClient(s.claude_code_model, s.claude_code_bin, s.claude_code_bridge_url,
                                s.claude_code_bridge_token, s.claude_code_timeout)
    if provider == "openrouter":
        from ripple.llm.openrouter import OpenRouterClient

        return OpenRouterClient(s.openrouter_api_key or "", s.openrouter_model, s.openrouter_base_url)
    if provider == "anthropic":
        from ripple.llm.anthropic_client import AnthropicClient

        return AnthropicClient(s.anthropic_api_key or "", s.ripple_model)
    if provider == "vertex":
        from ripple.llm.vertex import default_project, make_client

        project = s.vertex_project_id or default_project()
        if not project:
            raise LLMError("Vertex AI needs VERTEX_PROJECT_ID (or `gcloud config set project ...`)")
        return make_client(project, s.vertex_region, s.vertex_model, s.vertex_access_token)
    raise LLMError(f"no LLM provider available (RIPPLE_LLM_PROVIDER={s.ripple_llm_provider!r}); "
                   "install the `claude` CLI, log in to gcloud for vertex, "
                   "or set OPENROUTER_API_KEY / ANTHROPIC_API_KEY")


def log_call(provider: str, request: dict, response: Any, ms: float) -> None:
    """Append one request/response pair to RIPPLE_LLM_LOG_DIR, when it is set. Never raises."""
    d = get_settings().ripple_llm_log_dir
    if not d:
        return
    try:
        p = Path(d)
        p.mkdir(parents=True, exist_ok=True)
        name = f"{int(time.time() * 1000)}-{provider}-{os.getpid()}.json"
        (p / name).write_text(json.dumps({"provider": provider, "ms": ms, "request": request,
                                          "response": response}, default=str, indent=2))
    except Exception:  # noqa: BLE001 - logging must never break a call
        pass
