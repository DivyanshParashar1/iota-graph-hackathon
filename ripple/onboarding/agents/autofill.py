"""Demo-only Autofill: draft the company's answer to the agent's latest turn.

The chat counterpart of the data agent's `synthesize()`. It is a real LLM call through `ripple/llm`, and like
Synthesize it is an explicit demo affordance: the draft goes back to the user's message box (it is never sent
on their behalf), and the tenant is flagged `has_synthetic` because whatever is sent from it is invented.
"""

from __future__ import annotations

from ripple.db import TenantScope
from ripple.llm.base import LLMClient
from ripple.llm.structured import ask_model
from ripple.onboarding.agents.common import load_prompt, state_message
from ripple.onboarding.models import AutofillReply
from ripple.onboarding.store import current_brief, get_session, get_tenant, list_messages, set_tenant

RECENT = 12  # turns of the thread the drafter sees; the brief carries everything older


def autofill(scope: TenantScope, client: LLMClient, emit) -> AutofillReply:
    session = get_session(scope)
    messages = list_messages(scope, session["id"]) if session else []
    if not any(m.role == "agent" and m.text for m in messages):
        raise ValueError("there is no agent question to answer yet")
    tenant = get_tenant(scope) or {}
    brief, _ = current_brief(scope)
    thread = [{"speaker": (m.agent or "agent") if m.role == "agent" else "company", "stage": m.stage, "text": m.text}
              for m in messages[-RECENT:] if m.text and m.role != "system"]
    blocks = {"company": tenant.get("name", ""), "industry": tenant.get("industry", ""),
              "brief": brief.model_dump() if brief else {}, "conversation": thread}
    emit("llm", "autofill: drafting a demo answer")
    out, reply = ask_model(client, AutofillReply, load_prompt("autofill"),
                           [state_message("Conversation to answer", blocks,
                                          instruction="Draft the company's reply to the agent's latest message.")])
    set_tenant(scope, has_synthetic=True)
    emit("write", "autofill: drafted a demo answer (flagged synthetic)", ms=reply.ms, data={"note": out.note})
    return out
