"""Stage 2: the data agent and its in-chat forms.

One structured LLM call per turn (`DataTurn`). A turn either emits a new form round or reacts to the answers
of the last one. Forms are persisted before they are shown, answers are saved per field as the user types
(`routes_onboarding`), so a reload mid-form comes back with the partial values in place.

The agent never fills a value in itself (plan.md §4.2). `synthesize()` does, as an explicit demo affordance:
a separate LLM pass whose every value is stored with `source="synthetic"` and which flags the tenant.
"""

from __future__ import annotations

from typing import Any

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
from ripple.onboarding.models import (
    DataTurn,
    FormAnswer,
    FormSpec,
    Message,
    SynthesizedForm,
)
from ripple.onboarding.store import (
    append_message,
    apply_checklist_ops,
    current_brief,
    list_answers,
    list_checklist,
    list_forms,
    list_messages,
    open_form,
    save_answer,
    save_form,
    set_tenant,
)

AGENT = "data_agent"
STAGE = "data"
OPENING = ("Read the brief and emit your first form round: the backbone entities and their key properties. Ask "
           "in your reply whether they have any data exports to upload. Seed your checklist with what the "
           "ontology will still need.")
CONTINUE = ("Read the answers so far. Either emit the next, narrower form round, or set done when the data "
            "pack is enough to design the ontology. Do not repeat a question that is already answered.")


def _answers_by_form(scope: TenantScope) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for a in list_answers(scope):
        out.setdefault(a.form_id, []).append({"field_id": a.field_id, "value": a.value, "source": a.source,
                                              "confidence": a.confidence})
    return out


def turn(scope: TenantScope, sid: str, client: LLMClient, emit) -> dict:
    s = get_settings()
    brief, _ = current_brief(scope)
    forms = list_forms(scope)
    pending = open_form(scope)
    items = list_checklist(scope, STAGE)
    history = list_messages(scope, sid)
    first = not forms

    if pending and not first:
        # The user wrote something while a form is still open: answer them, do not pile on another round.
        emit("stage", f"{AGENT}: form {pending.id} still open")

    blocks = {
        "brief": brief.model_dump() if brief else {},
        "rounds_so_far": [{"id": f.id, "round": f.round, "title": f.title, "status": f.status,
                           "fields": [x.model_dump() for x in f.fields]} for f in forms],
        "answers": _answers_by_form(scope),
        "open_form_id": pending.id if pending else "",
        "checklist": checklist_block(items),
        "uploads": uploads_block(scope),
    }
    messages = conversation(history) if not first else []
    messages.append(state_message("Your working state", blocks, instruction=OPENING if first else CONTINUE))
    emit("llm", f"{AGENT}: thinking (round {len(forms) + 1})")
    out, reply = ask_model(client, DataTurn, load_prompt(AGENT), messages, effort=s.ripple_llm_effort)
    emit("llm", f"{AGENT}: replied", data={"done": out.done, "form": bool(out.form),
                                           "mappings": len(out.file_mappings)}, ms=reply.ms)

    if out.checklist_ops:
        apply_checklist_ops(scope, STAGE, out.checklist_ops)

    msgs: list[Message] = []
    form: FormSpec | None = None
    if out.form and not pending:
        form = save_form(scope, out.form.model_copy(update={"id": "", "round": len(forms) + 1,
                                                            "status": "open"}))
        emit("write", f"form round {form.round} with {len(form.fields)} fields", data={"form_id": form.id})
    text = out.reply.strip()
    if out.ask_for_files:
        text += "\n\nUseful uploads if you have them: " + ", ".join(out.ask_for_files)
    msgs.append(append_message(scope, sid, Message(
        role="agent", agent=AGENT, stage=STAGE, kind="form" if form else "text", text=text,
        payload={"id": form.id, "form": form.model_dump()} if form else
                {"file_mappings": [m.model_dump() for m in out.file_mappings],
                 "ask_for_files": out.ask_for_files})))

    if out.done and not form:
        emit("stage", f"{AGENT} finished: {out.done_reason}")
        return {"messages": msgs, "stage_done": True, "done_reason": out.done_reason}
    return {"messages": msgs, "stage_done": False}


# --------------------------------------------------------------------------- answers

def coerce(field_type: str, value: Any) -> Any:
    """Coerce a submitted value to the field's type. Raises ValueError on something unusable."""
    if value in (None, ""):
        return None
    if field_type in ("number", "currency", "percent"):
        v = float(str(value).replace(",", "").replace("%", "").strip())
        return v
    if field_type == "integer":
        return round(float(str(value).replace(",", "").strip()))
    if field_type == "boolean":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "y", "on")
    if field_type == "multiselect":
        return list(value) if isinstance(value, (list, tuple)) else [value]
    if field_type == "geo":
        if isinstance(value, dict):
            return {"lat": float(value["lat"]), "lon": float(value["lon"])} if "lat" in value else value
        return str(value)
    if field_type == "daterange":
        if isinstance(value, dict):
            return {"from": str(value.get("from", "")), "to": str(value.get("to", ""))}
        return str(value)
    if field_type == "group":
        if not isinstance(value, list):
            raise ValueError("a repeating group expects a list of rows")
        return value
    return value if isinstance(value, (list, dict)) else str(value)


def save_values(scope: TenantScope, form: FormSpec, values: dict[str, Any], *, source: str = "user",
                confidence: str = "exact", confidences: dict[str, str] | None = None) -> list[FormAnswer]:
    """Save (or overwrite) answers for a form. Unknown field ids are rejected; bad values raise ValueError."""
    fields = form.field_map()
    saved = []
    for fid, raw in values.items():
        f = fields.get(fid)
        if f is None:
            raise ValueError(f"form {form.id} has no field {fid!r}")
        value = coerce(f.type, raw)
        conf = (confidences or {}).get(fid) or confidence
        saved.append(save_answer(scope, FormAnswer(form_id=form.id, field_id=fid, value=value, source=source,
                                                   confidence=conf)))
    return saved


def missing_required(form: FormSpec, answers: dict[str, Any]) -> list[str]:
    """Required fields with no value, skipping fields hidden by their `show_if`."""
    out = []
    for f in form.fields:
        if f.show_if:
            target = f.show_if.get("field")
            if target and answers.get(target) != f.show_if.get("equals"):
                continue
        if f.required and answers.get(f.id) in (None, "", [], {}):
            out.append(f.id)
    return out


# --------------------------------------------------------------------------- demo-only synthesize

def synthesize(scope: TenantScope, form: FormSpec, client: LLMClient, emit) -> list[FormAnswer]:
    """Demo affordance: autofill a whole form with plausible values, every one marked synthetic."""
    brief, _ = current_brief(scope)
    blocks = {"brief": brief.model_dump() if brief else {},
              "form": {"title": form.title, "intro": form.intro,
                       "fields": [f.model_dump() for f in form.fields]}}
    emit("llm", "synthesize: inventing demo values")
    out, reply = ask_model(client, SynthesizedForm, load_prompt("synthesize"),
                           [state_message("Form to fill", blocks,
                                          instruction="Return one value per field id.")])
    fields = form.field_map()
    values = {k: v for k, v in (out.values or {}).items() if k in fields}
    saved = save_values(scope, form, values, source="synthetic", confidence="synthetic")
    set_tenant(scope, has_synthetic=True)
    emit("write", f"synthesized {len(saved)} values (all flagged synthetic)", ms=reply.ms,
         data={"note": out.note})
    return saved
