"""Structured output: ask for a pydantic model, get a validated instance, with one repair round.

`ask_model(client, model_cls, system, messages)` sends the model's JSON schema with the request. If the reply
does not validate, the validation errors are sent back as a user turn and the model gets one chance to fix it.
A second failure raises - agents never silently continue on an unparsed reply.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from ripple.config import get_settings
from ripple.llm.base import LLMClient, LLMError, Reply

T = TypeVar("T", bound=BaseModel)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def extract_json(text: str) -> dict | None:
    """The first JSON object in a reply (bare, fenced, or wrapped in prose)."""
    if not text:
        return None
    candidates = [text.strip()]
    m = _FENCE.search(text)
    if m:
        candidates.insert(0, m.group(1).strip())
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start:end + 1])
    for c in candidates:
        try:
            v = json.loads(c)
        except json.JSONDecodeError:
            continue
        if isinstance(v, dict):
            return v
    return None


def json_schema(model_cls: type[BaseModel]) -> dict:
    """A JSON schema for a pydantic model, flattened enough for strict structured-output modes."""
    schema = model_cls.model_json_schema()
    defs = schema.pop("$defs", {})
    return _inline(schema, defs)


def _inline(node: Any, defs: dict, depth: int = 0) -> Any:
    if depth > 24:
        return {"type": "object"}
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            target = defs.get(ref.split("/")[-1], {})
            merged = {**_inline(target, defs, depth + 1), **{k: v for k, v in node.items() if k != "$ref"}}
            return merged
        return {k: _inline(v, defs, depth + 1) for k, v in node.items()}
    if isinstance(node, list):
        return [_inline(v, defs, depth + 1) for v in node]
    return node


def _errors(e: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()[:12])


def parse_reply(reply: Reply, model_cls: type[T]) -> T:
    data = reply.data if reply.data is not None else extract_json(reply.text)
    if data is None:
        raise ValidationError.from_exception_data(model_cls.__name__, [])
    return model_cls.model_validate(data)


def ask_model(client: LLMClient, model_cls: type[T], system: str, messages: list[dict], *,
              effort: str | None = None, max_tokens: int | None = None, repairs: int = 1) -> tuple[T, Reply]:
    """One structured LLM call (plus up to `repairs` repair rounds). Returns (parsed, last reply)."""
    s = get_settings()
    schema = json_schema(model_cls)
    convo = list(messages)
    last_err = ""
    for attempt in range(repairs + 1):
        reply = client.complete(system=system, messages=convo, schema=schema,
                                effort=effort or s.ripple_llm_effort,
                                max_tokens=max_tokens or s.ripple_llm_max_tokens)
        try:
            return parse_reply(reply, model_cls), reply
        except ValidationError as e:
            last_err = _errors(e)
        except Exception as e:  # noqa: BLE001 - a non-dict reply, a truncated body
            last_err = str(e)
        if attempt == repairs:
            break
        convo = convo + [reply.assistant_message(),
                         {"role": "user", "content": f"That reply did not validate against the schema: {last_err}. "
                                                     "Send the corrected JSON object only."}]
    raise LLMError(f"{model_cls.__name__} did not validate after {repairs + 1} attempts: {last_err}")
