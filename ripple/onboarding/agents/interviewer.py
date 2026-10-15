"""Stage 1: the interviewer.

One structured LLM call per turn (`InterviewTurn`), then four writes to FalkorDB in a fixed order: checklist
ops, brief patch, the agent's reply as a `_Message`, and the step trail. The agent decides when the interview
is over; the stage machine holds that decision back while a core topic of the brief is still empty, and
reopens a checklist item instead (plan.md §4.1).
"""

from __future__ import annotations

from ripple.config import get_settings
from ripple.db import TenantScope
from ripple.llm.base import LLMClient
from ripple.llm.structured import ask_model
from ripple.onboarding.agents.common import (
    checklist_block,
    conversation,
    load_prompt,
    state_message,
    uploads_block,
)
from ripple.onboarding.models import Brief, InterviewTurn, Message
from ripple.onboarding.store import (
    append_message,
    apply_checklist_ops,
    current_brief,
    get_tenant,
    list_checklist,
    list_messages,
    put_brief,
    reopen_item,
)

AGENT = "interviewer"
STAGE = "interview"
OPENING = ("Open the interview. Introduce yourself in one sentence and ask your first three to five questions. "
           "Seed your checklist with the doubts you already have.")
CONTINUE = ("Read the latest user turn and respond. Resolve the checklist items it answered, add the doubts it "
            "raised, and patch the brief with what you learned.")


def turn(scope: TenantScope, sid: str, client: LLMClient, emit) -> dict:
    """One interviewer turn. Returns {messages, stage_done, done_reason}."""
    s = get_settings()
    tenant = get_tenant(scope) or {}
    brief, brief_row = current_brief(scope)
    brief = brief or Brief(company=tenant.get("name") or "", industry=tenant.get("industry") or "")
    items = list_checklist(scope, STAGE)
    history = list_messages(scope, sid)
    first = not any(m.role == "agent" and m.stage == STAGE for m in history)

    blocks = {
        "company": tenant.get("name") or "", "industry": tenant.get("industry") or "",
        "brief_so_far": brief.model_dump(), "checklist": checklist_block(items),
        "core_topics_still_empty": brief.core_gaps(), "uploads": uploads_block(scope),
    }
    messages = conversation(history) if not first else []
    messages.append(state_message("Your working state", blocks,
                                  instruction=OPENING if first else CONTINUE))
    emit("llm", f"{AGENT}: thinking ({len(items)} checklist items, {len(messages)} turns)")
    out, reply = ask_model(client, InterviewTurn, load_prompt(AGENT), messages, effort=s.ripple_llm_effort)
    emit("llm", f"{AGENT}: replied", data={"done": out.done, "ops": len(out.checklist_ops),
                                           "patch_keys": sorted(out.brief_patch)}, ms=reply.ms)

    if out.checklist_ops:
        apply_checklist_ops(scope, STAGE, out.checklist_ops)
    if out.brief_patch or not brief_row:
        brief = brief.merge(out.brief_patch)
        put_brief(scope, brief)
        if out.brief_patch:
            emit("write", f"brief patched: {', '.join(sorted(out.brief_patch))}")

    text = out.reply.strip()
    if out.ask_for_files:
        text += "\n\nIf you have any of these to hand, upload them: " + ", ".join(out.ask_for_files)
    msgs = [append_message(scope, sid, Message(role="agent", agent=AGENT, stage=STAGE, kind="text", text=text,
                                               payload={"ask_for_files": out.ask_for_files}))]

    if not out.done:
        return {"messages": msgs, "stage_done": False}

    gaps = brief.core_gaps()
    if gaps:
        question = ("Before we move on I still need the basics on: " + ", ".join(gaps)
                    + ". Could you fill those in?")
        reopen_item(scope, STAGE, question, "core topic of the brief is still empty")
        emit("stage", f"{AGENT} wanted to finish; core topics still empty: {gaps}", data={"gaps": gaps})
        msgs.append(append_message(scope, sid, Message(role="agent", agent=AGENT, stage=STAGE, kind="text",
                                                       text=question, payload={"core_gaps": gaps})))
        return {"messages": msgs, "stage_done": False}

    put_brief(scope, brief, approved=True,
              source_ids=[m.id for m in history if m.role == "user"][-20:])
    emit("stage", f"{AGENT} finished: {out.done_reason}", data={"done_reason": out.done_reason})
    return {"messages": msgs, "stage_done": True, "done_reason": out.done_reason}
