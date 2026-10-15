"""One tool-using agent loop, shared by every runtime agent (today: the expert runtime).

The loop is manual rather than an SDK tool runner because every call has to pass through the host: tool
results are recorded, each step is streamed to the UI, and the ids the model mentions are checked against the
ids that actually came back from tools.

    run_tool_loop(client, system="...", task="...", tools=[ToolSpec, ...], call=lambda name, args: ...)
      -> {"ok", "text", "turns", "ids", "steps"}
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import Any

from ripple.config import get_settings
from ripple.llm.base import LLMClient, LLMError

ID_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,15}-[A-Z0-9][A-Z0-9-]{1,23}\b")
RULES = ("Rules: answer only from tool results. Never invent an id: every id you mention must have appeared in "
         "a tool result in this conversation. The tenant is fixed by the server; tools never take a tenant.")
MAX_RESULT_CHARS = 12000


def extract_ids(text: str) -> set[str]:
    return set(ID_RE.findall(text or ""))


def _result_text(value: Any) -> str:
    s = value if isinstance(value, str) else json.dumps(value, default=str)
    return s if len(s) <= MAX_RESULT_CHARS else s[:MAX_RESULT_CHARS] + "...(truncated)"


def run_tool_loop(client: LLMClient, *, system: str, task: str, tools: list[dict],
                  call: Callable[[str, dict], Any], on_step: Callable[[dict], None] | None = None,
                  max_turns: int = 8, validate_ids: bool = True, seen_ids: set[str] | None = None,
                  effort: str | None = None) -> dict:
    """Run one agent to a final answer. `call(name, args)` runs a tool and returns anything JSON-serialisable
    (a dict with a `node_ids` list feeds the id validator)."""
    s = get_settings()
    allowed = {t["name"] for t in tools}
    seen: set[str] = set(seen_ids or set())
    messages: list[dict] = [{"role": "user", "content": task}]
    steps: list[dict] = []
    repairs = 0

    def step(kind: str, **kw) -> None:
        ev = {"kind": kind, "ts": int(time.time() * 1000), **kw}
        steps.append(ev)
        if on_step:
            on_step(ev)

    for turn in range(max_turns):
        try:
            reply = client.complete(system=f"{system}\n\n{RULES}", messages=messages, tools=tools,
                                    effort=effort or s.ripple_llm_effort, max_tokens=s.ripple_llm_max_tokens)
        except LLMError as e:
            step("error", summary=str(e))
            return {"ok": False, "text": "", "reason": str(e), "turns": turn, "ids": sorted(seen), "steps": steps}
        if not reply.tool_calls:
            text = reply.text.strip()
            bad = sorted(extract_ids(text) - seen) if validate_ids else []
            if not bad:
                step("answer", summary=text[:400])
                return {"ok": True, "text": text, "reason": "", "turns": turn + 1, "ids": sorted(seen),
                        "steps": steps}
            step("error", summary=f"id validator rejected {bad[:5]}", data={"bad_ids": bad, "fatal": False})
            if repairs >= 1:
                return {"ok": False, "text": text, "reason": f"validator: {bad}", "turns": turn + 1,
                        "ids": sorted(seen), "steps": steps}
            repairs += 1
            messages += [reply.assistant_message(),
                         {"role": "user", "content": f"These ids are in no tool result: {bad}. Rewrite your answer "
                                                     "using only ids that appeared in tool results."}]
            continue
        messages.append(reply.assistant_message())
        results = []
        for c in reply.tool_calls:
            if c.name not in allowed:
                results.append({"type": "tool_result", "tool_use_id": c.id, "is_error": True,
                                "content": f"Tool {c.name} is not available here. Available: {sorted(allowed)}"})
                continue
            step("tool_call", tool=c.name, args=c.input)
            try:
                out = call(c.name, c.input)
            except Exception as e:  # noqa: BLE001 - tool errors go back to the model
                step("tool_error", tool=c.name, summary=str(e)[:400])
                results.append({"type": "tool_result", "tool_use_id": c.id, "is_error": True,
                                "content": f"Error: {e}"})
                continue
            if isinstance(out, dict):
                seen |= {str(i) for i in (out.get("node_ids") or [])}
            step("tool_result", tool=c.name, summary=(out.get("summary", "") if isinstance(out, dict) else "")[:400])
            results.append({"type": "tool_result", "tool_use_id": c.id, "content": _result_text(out)})
        messages.append({"role": "user", "content": results})
    return {"ok": False, "text": "", "reason": "max turns", "turns": max_turns, "ids": sorted(seen), "steps": steps}
