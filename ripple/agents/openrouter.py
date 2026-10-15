"""OpenRouter client with the Anthropic `messages.create` surface, so the tool loop in llm.py runs unchanged.

Requests are translated to OpenRouter's OpenAI-compatible chat completions API (system prompt, tools,
tool_use / tool_result blocks), and responses back to Anthropic-shaped blocks. The model always comes from
OPENROUTER_MODEL (e.g. anthropic/claude-opus-5.5). Reasoning details are carried on the assistant turn and sent
back verbatim, which OpenRouter needs for reasoning models in multi-turn tool use.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import httpx

_STOP = {"tool_calls": "tool_use", "length": "max_tokens", "stop": "end_turn"}


def _get(b: Any, k: str, default=None):
    return b.get(k, default) if isinstance(b, dict) else getattr(b, k, default)


def _to_openai_messages(system: str | None, messages: list[dict]) -> list[dict]:
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
                      "function": {"name": _get(b, "name"), "arguments": json.dumps(_get(b, "input") or {})}}
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


def _to_anthropic_response(data: dict) -> SimpleNamespace:
    choice = data["choices"][0]
    msg = choice.get("message") or {}
    content = []
    if msg.get("reasoning_details"):
        content.append(SimpleNamespace(type="reasoning", details=msg["reasoning_details"]))
    if msg.get("content"):
        content.append(SimpleNamespace(type="text", text=msg["content"]))
    for c in msg.get("tool_calls") or []:
        try:
            args = json.loads(c["function"].get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        content.append(SimpleNamespace(type="tool_use", id=c["id"], name=c["function"]["name"], input=args))
    stop = "tool_use" if any(b.type == "tool_use" for b in content) else _STOP.get(choice.get("finish_reason"), "end_turn")
    return SimpleNamespace(content=content, stop_reason=stop, model=data.get("model"))


class OpenRouterClient:
    """`client.messages.create(**anthropic_kwargs)` against OpenRouter."""

    def __init__(self, api_key: str, model: str, base_url: str = "https://openrouter.ai/api/v1",
                 http: httpx.Client | None = None, timeout: float = 300):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.messages = self
        self._http = http or httpx.Client(timeout=timeout)
        self._headers = {"Authorization": f"Bearer {api_key}", "X-Title": "Ripple"}

    def payload(self, **kw) -> dict:
        body: dict = {"model": self.model, "max_tokens": kw.get("max_tokens", 4096),
                      "messages": _to_openai_messages(kw.get("system"), kw.get("messages", []))}
        if kw.get("tools"):
            body["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                               "parameters": t["input_schema"]}} for t in kw["tools"]]
            body["tool_choice"] = "auto"
        effort = (kw.get("output_config") or {}).get("effort")
        if kw.get("thinking") or effort:
            body["reasoning"] = {"effort": effort or "medium"}
        return body

    def create(self, **kw) -> SimpleNamespace:
        r = self._http.post(f"{self.base_url}/chat/completions", headers=self._headers, json=self.payload(**kw))
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"OpenRouter error: {data['error']}")
        return _to_anthropic_response(data)
