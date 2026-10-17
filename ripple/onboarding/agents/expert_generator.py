"""Stage 4: the expert generator.

The agent invents the roles this supply chain needs. Every role has to earn its place: a role whose
`focus_types` are not in the approved spec, or whose justification names no ontology type, is rejected and the
agent is asked to drop or merge it (plan.md §4.4). Approval is per role, in `routes_experts`.
"""

from __future__ import annotations

import re

from ripple.config import get_settings
from ripple.db import TenantScope
from ripple.experts.store import export_role
from ripple.llm.base import LLMClient
from ripple.llm.structured import ask_model
from ripple.onboarding.agents.common import conversation, load_prompt, state_message, user_spoke_last
from ripple.onboarding.models import ExpertRole, ExpertsTurn, Message
from ripple.onboarding.store import (
    append_message,
    approved_spec,
    current_brief,
    delete_expert,
    list_experts,
    list_messages,
    save_expert,
)

AGENT = "expert_generator"
STAGE = "experts"
REPAIRS = 2
MIN_PROMPT_CHARS = 400
OPENING = ("Decide which expert roles this company needs and write them. Justify each one against the approved "
           "ontology.")
CONTINUE = ("The user has asked for a change to the roles. Return the full set of roles you want to stand "
            "behind now - including the unchanged ones - and say what you changed.")
REENTER = ("The approved ontology changed since these roles were written, so they are stale. Return the full set of "
           "roles that fits the ontology now - including the unchanged ones - and say what you changed.")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")


def validate_roles(roles: list[ExpertRole], spec) -> list[str]:
    """Problems that make a role unapprovable. One message per problem, named by role."""
    errors: list[str] = []
    labels = {t.label for t in spec.types}
    rels = {r.type for r in spec.relationships}
    seen: set[str] = set()
    if not roles:
        errors.append("no roles were generated")
    for r in roles:
        who = r.name or r.title or "<unnamed>"
        if not NAME_RE.match(r.name or ""):
            errors.append(f"{who}: name must be snake_case")
        if r.name in seen:
            errors.append(f"{who}: duplicate role name")
        seen.add(r.name)
        if not r.mandate.strip():
            errors.append(f"{who}: no mandate")
        bad = [t for t in r.focus_types if t not in labels]
        if bad:
            errors.append(f"{who}: focus_types {bad} are not in the approved ontology")
        bad_rels = [t for t in r.focus_relationships if t not in rels]
        if bad_rels:
            errors.append(f"{who}: focus_relationships {bad_rels} are not in the approved ontology")
        if not r.focus_types:
            errors.append(f"{who}: a role with no ontology footprint - drop it or merge it into another")
        if not any(label in r.justification for label in labels):
            errors.append(f"{who}: the justification names no ontology type")
        if len(r.system_prompt.strip()) < MIN_PROMPT_CHARS:
            errors.append(f"{who}: system_prompt is too short to run as-is "
                          f"({len(r.system_prompt.strip())} chars)")
        if not r.playbook:
            errors.append(f"{who}: no playbook questions")
    return errors


def turn(scope: TenantScope, sid: str, client: LLMClient, emit) -> dict:
    s = get_settings()
    spec, spec_row = approved_spec(scope)
    if spec is None:
        msgs = [append_message(scope, sid, Message(
            role="system", stage=STAGE, kind="system",
            text="The ontology has to be approved before the expert roles can be designed."))]
        return {"messages": msgs, "stage_done": False}
    brief, _ = current_brief(scope)
    existing = list_experts(scope)
    history = list_messages(scope, sid)
    first = not existing

    blocks = {"brief": brief.model_dump() if brief else {}, "ontology": spec.model_dump(by_alias=True),
              "existing_roles": [{"name": e.name, "title": e.title, "status": e.status, "stale": e.stale,
                                  "mandate": e.mandate} for e in existing]}
    messages = conversation(history) if not first else []
    messages.append(state_message("Brief and approved ontology", blocks,
                                  instruction=OPENING if first else
                                  CONTINUE if user_spoke_last(history) else REENTER))

    out = None
    errors: list[str] = []
    for attempt in range(REPAIRS + 1):
        emit("llm", f"{AGENT}: designing roles" + (f" (repair {attempt})" if attempt else ""))
        out, reply = ask_model(client, ExpertsTurn, load_prompt(AGENT), messages, effort=s.ripple_llm_effort)
        errors = validate_roles(out.roles, spec)
        if not errors:
            emit("llm", f"{AGENT}: {len(out.roles)} roles", ms=reply.ms,
                 data={"roles": [r.name for r in out.roles]})
            break
        emit("error", f"{AGENT}: {len(errors)} roles rejected", data={"errors": errors[:12]})
        if attempt == REPAIRS:
            break
        messages = [*messages, reply.assistant_message(),
                    {"role": "user", "content": "These roles were rejected:\n- " + "\n- ".join(errors[:20])
                                                + "\nReturn the full corrected set of roles."}]
    if out is None or errors:
        msgs = [append_message(scope, sid, Message(
            role="system", stage=STAGE, kind="system",
            text="The expert generator could not produce a valid set of roles. Ask it for a change, or edit "
                 "the ontology.", payload={"errors": errors[:20]}))]
        return {"messages": msgs, "stage_done": False}

    kept = []
    for r in out.roles:
        prev = next((e for e in existing if e.name == r.name), None)
        role = r.model_copy(update={"id": prev.id if prev else f"EXP-{r.name}",
                                    "status": "draft", "origin": "generated", "stale": False,
                                    "version": (prev.version + 1) if prev else 1})
        saved = save_expert(scope, role)
        export_role(scope, saved)
        kept.append(saved)
    # The set returned is the whole set: a generated draft it left out is withdrawn. A role the user approved or
    # wrote stays until the user removes it.
    names = {r.name for r in out.roles}
    withdrawn = [e for e in existing if e.name not in names and e.origin == "generated" and e.status == "draft"]
    for e in withdrawn:
        delete_expert(scope, e.id)
    emit("write", f"{len(kept)} roles saved as drafts", data={"roles": [r.name for r in kept],
                                                               "withdrawn": [e.name for e in withdrawn]})

    text = out.reply.strip()
    if out.dropped:
        text += "\n\nConsidered and dropped: " + "; ".join(out.dropped)
    msgs = [append_message(scope, sid, Message(
        role="agent", agent=AGENT, stage=STAGE, kind="artifact", text=text,
        payload={"roles": [{"id": r.id, "name": r.name, "title": r.title} for r in kept],
                 "dropped": out.dropped, "spec_version": (spec_row or {}).get("version")}))]
    return {"messages": msgs, "stage_done": False}  # the user approves role by role
