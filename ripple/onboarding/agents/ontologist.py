"""Stage 3: the ontology agent.

A turn drafts (or revises) the spec, validates it, and shows it for review. A spec that fails validation goes
straight back to the agent with the list of errors - up to `REPAIRS` times - because a spec the user cannot
approve is not worth showing.

Approval is the user's, and happens in `routes_ontology`: it calls `approve()` here, which applies the indexes
and then asks the agent for the instance data in terms of the approved spec and loads it with provenance.
"""

from __future__ import annotations

from ripple.config import get_settings
from ripple.db import TenantScope
from ripple.graph.apply import apply_spec, load_instances
from ripple.llm.base import LLMClient, get_client
from ripple.llm.structured import ask_model
from ripple.onboarding.agents.common import conversation, load_prompt, state_message, uploads_block
from ripple.onboarding.models import InstanceBatch, Message, OntologySpec, OntologyTurn
from ripple.onboarding.store import (
    append_message,
    current_brief,
    current_spec,
    list_answers,
    list_forms,
    list_messages,
    save_spec,
    set_spec_status,
)
from ripple.onboarding.validate import SpecInvalid, validate_spec

AGENT = "ontologist"
STAGE = "ontology"
REPAIRS = 2
OPENING = ("Design the ontology for this company from the brief and the data pack. Return the whole spec and "
           "explain it in your reply.")
CONTINUE = ("The user has asked for a change. Return the whole revised spec with the change applied and say "
            "what you changed.")
EXTRACT = ("Turn the data pack into instance data for the approved spec: one node per real thing the user told "
           "us about, with the properties they gave, and the edges between them. Use the spec's id_patterns to "
           "mint ids. Put the ids of the form answers (ANS-...) or uploads (ATT-...) a node came from in its "
           "source_ids. Do not invent entities the data pack does not mention, and do not invent property "
           "values - leave a property out when it is unknown.")


def _data_pack(scope: TenantScope) -> dict:
    answers = list_answers(scope)
    forms = {f.id: f for f in list_forms(scope)}
    rows = []
    for a in answers:
        field = forms.get(a.form_id).field_map().get(a.field_id) if forms.get(a.form_id) else None
        rows.append({"answer_id": a.id, "form_id": a.form_id, "field_id": a.field_id,
                     "label": field.label if field else a.field_id,
                     "type": field.type if field else "", "unit": field.unit if field else "",
                     "maps_to": field.maps_to if field else "", "value": a.value,
                     "source": a.source, "confidence": a.confidence})
    return {"answers": rows, "uploads": uploads_block(scope)}


def turn(scope: TenantScope, sid: str, client: LLMClient, emit) -> dict:
    s = get_settings()
    brief, _ = current_brief(scope)
    spec, spec_row = current_spec(scope)
    history = list_messages(scope, sid)
    first = spec is None

    blocks = {"brief": brief.model_dump() if brief else {}, "data_pack": _data_pack(scope),
              "current_spec": spec.model_dump(by_alias=True) if spec else None,
              "current_status": (spec_row or {}).get("status", "")}
    messages = conversation(history) if not first else []
    messages.append(state_message("Brief, data pack and current spec", blocks,
                                  instruction=OPENING if first else CONTINUE))

    out = None
    errors: list[str] = []
    for attempt in range(REPAIRS + 1):
        emit("llm", f"{AGENT}: drafting the ontology" + (f" (repair {attempt})" if attempt else ""))
        out, reply = ask_model(client, OntologyTurn, load_prompt(AGENT), messages, effort=s.ripple_llm_effort)
        errors = validate_spec(out.spec)
        if not errors:
            emit("llm", f"{AGENT}: {len(out.spec.types)} types, {len(out.spec.relationships)} relationships",
                 ms=reply.ms)
            break
        emit("error", f"{AGENT}: spec invalid ({len(errors)} problems)", data={"errors": errors[:12]})
        if attempt == REPAIRS:
            break
        messages = messages + [reply.assistant_message(),
                               {"role": "user", "content": "The spec was rejected by validation:\n- "
                                + "\n- ".join(errors[:20]) + "\nReturn the whole corrected spec."}]
    if out is None or errors:
        msgs = [append_message(scope, sid, Message(
            role="system", stage=STAGE, kind="system",
            text="The ontology agent could not produce a valid spec. Ask it for a change, or go back to the "
                 "data stage and fill in more detail.", payload={"errors": errors[:20]}))]
        return {"messages": msgs, "stage_done": False}

    row = save_spec(scope, out.spec, status="draft", rationale=out.spec.rationale,
                    source_ids=_source_ids(scope), new_version=not first)
    emit("write", f"spec v{row['version']} saved as draft", data={"spec_id": row["id"]})
    text = out.reply.strip()
    if out.questions:
        text += "\n\nOpen choices: " + "; ".join(out.questions)
    msgs = [append_message(scope, sid, Message(
        role="agent", agent=AGENT, stage=STAGE, kind="artifact", text=text,
        payload={"spec_id": row["id"], "version": row["version"], "types": len(out.spec.types),
                 "relationships": len(out.spec.relationships), "questions": out.questions}))]
    return {"messages": msgs, "stage_done": False}  # the user approves; approve() advances the stage


def _source_ids(scope: TenantScope) -> list[str]:
    ids = [a.id for a in list_answers(scope)][:200]
    ids += [a["id"] for a in uploads_block(scope)]
    ids += [f.id for f in list_forms(scope)]
    return ids


def approve(scope: TenantScope, sid: str, emit, *, client: LLMClient | None = None,
            spec: OntologySpec | None = None) -> dict:
    """Validate, apply the indexes, extract the instance data and load it. Raises SpecInvalid on a bad spec."""
    current, row = current_spec(scope)
    spec = spec or current
    if spec is None or row is None:
        raise SpecInvalid(["there is no ontology spec to approve"])
    errors = validate_spec(spec)
    if errors:
        raise SpecInvalid(errors)
    set_spec_status(scope, row["id"], "approved")
    applied = apply_spec(scope, spec)
    emit("write", f"indexes applied ({applied['indexes_created']} new)", data=applied)

    client = client or get_client()
    blocks = {"spec": spec.model_dump(by_alias=True), "data_pack": _data_pack(scope)}
    emit("llm", f"{AGENT}: reading the data pack into the approved ontology")
    batch, reply = ask_model(client, InstanceBatch, load_prompt(AGENT),
                             [state_message("Approved spec and data pack", blocks, instruction=EXTRACT)])
    loaded = load_instances(scope, spec, batch, wipe=True)
    emit("write", f"loaded {loaded['nodes']} nodes and {loaded['edges']} edges", ms=reply.ms, data=loaded)
    append_message(scope, sid, Message(
        role="agent", agent=AGENT, stage=STAGE, kind="artifact",
        text=f"Ontology v{row['version']} approved: {applied['types']} types, "
             f"{applied['relationships']} relationships. Loaded {loaded['nodes']} nodes and "
             f"{loaded['edges']} edges from the data pack.",
        payload={"spec_id": row["id"], "applied": applied, "loaded": loaded, "notes": batch.notes}))
    return {"spec_id": row["id"], "version": row["version"], **applied, **loaded}
