"""OpenRouter provider (selectable with RIPPLE_LLM_PROVIDER=openrouter).

Requests are translated to OpenRouter's OpenAI-compatible chat completions API: system prompt, tools,
tool_use / tool_result blocks, and `response_format: json_schema` for structured output. Reasoning details are
carried on the assistant turn and sent back verbatim, which OpenRouter needs for reasoning models in multi-turn
tool use.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from ripple.llm.base import LLMError, Reply, ToolCall, log_call

_STOP = {"tool_calls": "tool_use", "length": "max_tokens", "stop": "end_turn",
         "malformed_function_call": "malformed_function_call"}  # Gemini's tool-call misfire; retried on Vertex


def _get(b: Any, k: str, default=None):
    return b.get(k, default) if isinstance(b, dict) else getattr(b, k, default)


def to_openai_messages(system: str | None, messages: list[dict]) -> list[dict]:
    out: list[dict] = [{"role": "system", "content": system}] if system else []
    for m in messages:
        content = m["content"]
        if isinstance(content, str):
            out.append({"role": m["role"], "content": content})
            continue
        if m["role"] == "assistant":
            text = "\n".join(_get(b, "text", "") for b in content if _get(b, "type") == "text")
            msg: dict = {"role": "assistant", "content": text or None}
            calls = [{"id": _get(b, "id"), "type": "function",
                      "function": {"name": _get(b, "name"), "arguments": json.dumps(_get(b, "input") or {})},
                      **({"extra_content": _get(b, "extra_content")} if _get(b, "extra_content") else {})}
                     for b in content if _get(b, "type") == "tool_use"]
            if calls:
                msg["tool_calls"] = calls
            details = [d for b in content if _get(b, "type") == "reasoning" for d in _get(b, "details", [])]
            if details:
                msg["reasoning_details"] = details
            out.append(msg)
            continue
        texts = []
        for b in content:  # user turn: tool results become role=tool messages
            if _get(b, "type") == "tool_result":
                body = _get(b, "content", "")
                if not isinstance(body, str):
                    body = json.dumps(body, default=str)
                out.append({"role": "tool", "tool_call_id": _get(b, "tool_use_id"),
                            "content": f"ERROR: {body}" if _get(b, "is_error") else body})
            elif _get(b, "type") == "text":
                texts.append(_get(b, "text", ""))
        if texts:
            out.append({"role": "user", "content": "\n".join(texts)})
    return out


class OpenRouterClient:
    """`complete(...)` against OpenRouter."""

    name = "openrouter"

    def __init__(self, api_key: str, model: str, base_url: str = "https://openrouter.ai/api/v1",
                 http: httpx.Client | None = None, timeout: float = 600):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=timeout)
        self._headers = {"Authorization": f"Bearer {api_key}", "X-Title": "Ripple"}

    def payload(self, system: str, messages: list[dict], tools: list[dict] | None, schema: dict | None,
                max_tokens: int | None, effort: str | None) -> dict:
        body: dict = {"model": self.model, "max_tokens": max_tokens or 16000,
                      "messages": to_openai_messages(system, messages)}
        if tools:
            body["tools"] = [{"type": "function",
                              "function": {"name": t["name"], "description": t.get("description", ""),
                                           "parameters": t.get("input_schema") or t.get("schema") or {}}}
                             for t in tools]
            body["tool_choice"] = "auto"
        elif schema:
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "reply", "strict": True, "schema": schema}}
        if effort:
            body["reasoning"] = {"effort": effort}
        return body

    def complete(self, *, system: str = "", messages: list[dict], tools: list[dict] | None = None,
                 schema: dict | None = None, max_tokens: int | None = None, effort: str | None = None) -> Reply:
        body = self.payload(system, messages, tools, schema, max_tokens, effort)
        t0 = time.perf_counter()
        try:
            r = self._http.post(f"{self.base_url}/chat/completions", headers=self._headers, json=body)
            r.raise_for_status()
            data = r.json()
        except Exception as e:  # noqa: BLE001
            raise LLMError(f"{self.name} request failed: {e}") from None
        ms = round((time.perf_counter() - t0) * 1000, 1)
        log_call(self.name, body, data, ms)
        if "error" in data:
            raise LLMError(f"OpenRouter error: {data['error']}")
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        reply = Reply(text=msg.get("content") or "", model=data.get("model") or self.model,
                      usage=data.get("usage") or {}, ms=ms)
        for c in msg.get("tool_calls") or []:
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            reply.tool_calls.append(ToolCall(c["id"], c["function"]["name"], args, c.get("extra_content") or {}))
        reply.stop_reason = ("tool_use" if reply.tool_calls
                             else _STOP.get(choice.get("finish_reason"), "end_turn"))
        if schema and not tools and reply.text:
            from ripple.llm.structured import extract_json

            reply.data = extract_json(reply.text)
        return reply
