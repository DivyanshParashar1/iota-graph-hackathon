"""LLM mode: a manual Claude tool-use loop over registry tools, with per-call logging, event emission, tenant
scoping (tools run through the AgentRun's TenantScope) and an ID validator. FakeAnthropic replays scripted
responses so the loop is tested without a key. The client is Anthropic's SDK, OpenRouterClient or ClaudeCodeClient
(same surface).

Manual loop (not the SDK tool runner) because every call must go through AgentRun.call: ToolCall logging,
SSE events and the seen-id set for the validator.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from ripple.agents.events import slim
from ripple.agents.runtime import AgentRun, extract_ids
from ripple.config import get_settings
from ripple.ontology import summary_text
from ripple.tools.registry import TOOLS

_CLIENT_OVERRIDE: Any = None
RULES = ("Rules: use the tools; never invent ids. Every id you mention (SUP-..., ORD-..., INC-..., DOC-...) must "
         "appear in a tool result from this conversation. The tenant is fixed by the server; tools never take a "
         "tenant. Keep the final answer under 120 words.")


def set_client(client) -> None:
    """Install a client (e.g. FakeAnthropic) for tests; None restores the default."""
    global _CLIENT_OVERRIDE
    _CLIENT_OVERRIDE = client


def get_client():
    if _CLIENT_OVERRIDE is not None:
        return _CLIENT_OVERRIDE
    s = get_settings()
    if s.llm_provider == "claude_code":
        from ripple.agents.claude_code import ClaudeCodeClient

        return ClaudeCodeClient(s.claude_code_model, s.claude_code_bin, s.claude_code_bridge_url,
                                s.claude_code_bridge_token, s.claude_code_timeout)
    if s.llm_provider == "openrouter":
        from ripple.agents.openrouter import OpenRouterClient

        return OpenRouterClient(s.openrouter_api_key, s.openrouter_model, s.openrouter_base_url)
    if s.llm_provider != "anthropic":
        return None
    import anthropic

    return anthropic.Anthropic(api_key=s.anthropic_api_key)


class FakeAnthropic:
    """Test double for anthropic.Anthropic: `client.messages.create(**kw)` pops the next scripted response.

    script: list of responses; each is a list of blocks ({"type": "text", "text": ...} or
    {"type": "tool_use", "name": ..., "input": {...}}) or a callable(kwargs) -> blocks.
    """

    def __init__(self, script: list | None = None, default_text: str = "Done."):
        self.script = list(script or [])
        self.default_text = default_text
        self.calls: list[dict] = []
        self.messages = self
        self._n = 0

    def create(self, **kw):
        self.calls.append({**kw, "messages": list(kw.get("messages", []))})  # snapshot: the caller keeps appending
        blocks = self.script.pop(0) if self.script else [{"type": "text", "text": self.default_text}]
        if callable(blocks):
            blocks = blocks(kw)
        content = []
        for b in blocks:
            if b["type"] == "tool_use":
                self._n += 1
                content.append(SimpleNamespace(type="tool_use", id=f"toolu_{self._n:04d}", name=b["name"],
                                               input=b.get("input", {})))
            else:
                content.append(SimpleNamespace(type="text", text=b["text"]))
        stop = "tool_use" if any(c.type == "tool_use" for c in content) else "end_turn"
        return SimpleNamespace(content=content, stop_reason=stop, model=kw.get("model"))


def _tool_content(res) -> str:
    body = {"summary": res.summary, "node_ids": res.node_ids[:60], "data": slim(res.data)}
    s = json.dumps(body, default=str)
    return s if len(s) < 12000 else s[:12000] + "...(truncated)"


def _text(content) -> str:
    return "\n".join(getattr(b, "text", "") for b in content if getattr(b, "type", "") == "text").strip()


def run_llm_agent(run: AgentRun, agent: str, role: str, task: str, tool_names: list[str], client=None,
                  max_turns: int = 12) -> dict:
    """Run one agent as a Claude tool-use loop. Returns {ok, text, reason, turns}."""
    client = client or get_client()
    if client is None:
        return {"ok": False, "text": "", "reason": "no client", "turns": 0}
    s = get_settings()
    tools = [TOOLS[n].anthropic() for n in tool_names if n in TOOLS]
    system = f"{role}\n\nOntology:\n{summary_text()}\n\n{RULES}"
    messages: list[dict] = [{"role": "user", "content": task}]
    fixes = 0
    for turn in range(max_turns):
        try:
            resp = client.messages.create(model=s.ripple_model, max_tokens=16000, system=system, tools=tools,
                                          tool_choice={"type": "auto"}, thinking={"type": "adaptive"},
                                          output_config={"effort": "medium"}, messages=messages)
        except Exception as e:  # noqa: BLE001 - provider/network errors fall back to scripted
            return {"ok": False, "text": "", "reason": f"LLM error: {e}", "turns": turn}
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        uses = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
        if not uses:
            text = _text(resp.content)
            bad = sorted(extract_ids(text) - run.seen)
            if not bad:
                run.message(agent, text, sorted(extract_ids(text)), data={"mode": "llm"})
                return {"ok": True, "text": text, "reason": "", "turns": turn + 1}
            run.emit(agent, "error", summary=f"ID validator rejected {bad[:5]}", data={"fatal": False, "bad_ids": bad})
            if fixes >= 1:
                return {"ok": False, "text": text, "reason": f"validator: {bad}", "turns": turn + 1}
            fixes += 1
            messages.append({"role": "assistant", "content": resp.content})
            messages.append({"role": "user", "content": f"These ids are not in any tool result: {bad}. Rewrite your "
                                                        "answer using only ids that appeared in tool results."})
            continue
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for b in uses:
            if b.name not in tool_names:
                results.append({"type": "tool_result", "tool_use_id": b.id, "is_error": True,
                                "content": f"Tool {b.name} is not available to {agent}."})
                continue
            try:
                res = run.call(agent, b.name, **dict(b.input or {}))
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": _tool_content(res)})
            except Exception as e:  # noqa: BLE001 - tool errors go back to the model
                results.append({"type": "tool_result", "tool_use_id": b.id, "is_error": True, "content": f"Error: {e}"})
        messages.append({"role": "user", "content": results})  # all results of this turn in one message
    return {"ok": False, "text": "", "reason": "max turns", "turns": max_turns}


def compose_answer(question: str, draft: str, tool_results: list[dict], allowed_ids: set[str]) -> str | None:
    """Brain answers in LLM mode: Claude rewrites the scripted draft from the same tool results; validated."""
    client = get_client()
    if client is None:
        return None
    s = get_settings()
    ctx = json.dumps([{"summary": r.get("summary"), "data": slim(r.get("data"))} for r in tool_results], default=str)[:20000]
    messages = [{"role": "user", "content": f"Question: {question}\n\nDraft answer: {draft}\n\nTool results: {ctx}\n\n"
                                            "Write a clear answer (max 120 words) using only these facts; keep ids."}]
    allowed = set(allowed_ids) | extract_ids(draft)
    for _ in range(2):
        try:
            resp = client.messages.create(model=s.ripple_model, max_tokens=16000, system=RULES,
                                          thinking={"type": "adaptive"}, output_config={"effort": "medium"},
                                          messages=messages)
        except Exception:  # noqa: BLE001 - keep the scripted draft
            return None
        text = _text(resp.content)
        bad = sorted(extract_ids(text) - allowed)
        if text and not bad:
            return text
        messages += [{"role": "assistant", "content": resp.content},
                     {"role": "user", "content": f"Remove or fix these ids, they are not in the tool results: {bad}"}]
    return None
