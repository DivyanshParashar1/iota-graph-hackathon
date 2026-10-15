"""The Anthropic API provider (RIPPLE_LLM_PROVIDER=anthropic). Kept because it is a thin wrapper: the SDK is
already pinned, and it is the fallback when neither the Claude Code login nor OpenRouter is available.

Structured output is requested the portable way - the schema goes into the prompt and the JSON is extracted and
validated by `ripple.llm.structured` - so no provider-specific output API is relied on here.
"""

from __future__ import annotations

import json
import time

from ripple.llm.base import LLMError, Reply, ToolCall, log_call

SCHEMA_RULE = ("Reply with a single JSON object and nothing else - no prose, no code fence. It must validate "
               "against this JSON schema:\n{schema}")


class AnthropicClient:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, client=None):
        import anthropic

        self.model = model
        self._c = client or anthropic.Anthropic(api_key=api_key)

    def complete(self, *, system: str = "", messages: list[dict], tools: list[dict] | None = None,
                 schema: dict | None = None, max_tokens: int | None = None, effort: str | None = None) -> Reply:
        from ripple.llm.structured import extract_json

        sys_text = system
        if schema and not tools:
            sys_text = f"{system}\n\n{SCHEMA_RULE.format(schema=json.dumps(schema))}"
        kw: dict = {"model": self.model, "max_tokens": max_tokens or 16000, "system": sys_text,
                    "messages": messages, "thinking": {"type": "adaptive"}}
        if effort:
            kw["output_config"] = {"effort": effort}
        if tools:
            kw["tools"] = [{"name": t["name"], "description": t.get("description", ""),
                            "input_schema": t.get("input_schema") or t.get("schema") or {}} for t in tools]
            kw["tool_choice"] = {"type": "auto"}
        t0 = time.perf_counter()
        try:
            resp = self._c.messages.create(**kw)
        except Exception as e:  # noqa: BLE001
            raise LLMError(f"Anthropic request failed: {e}") from None
        ms = round((time.perf_counter() - t0) * 1000, 1)
        log_call(self.name, {k: v for k, v in kw.items() if k != "messages"}, str(resp)[:4000], ms)
        text = "\n".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text").strip()
        reply = Reply(text=text, model=getattr(resp, "model", self.model), ms=ms,
                      stop_reason=getattr(resp, "stop_reason", "end_turn") or "end_turn")
        for b in resp.content:
            if getattr(b, "type", "") == "tool_use":
                reply.tool_calls.append(ToolCall(b.id, b.name, dict(b.input or {})))
        if reply.tool_calls:
            reply.stop_reason = "tool_use"
        if schema and not tools:
            reply.data = extract_json(text)
        return reply
