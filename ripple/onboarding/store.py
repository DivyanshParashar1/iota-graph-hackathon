"""Every read and write of onboarding state in FalkorDB.

Nothing else in `ripple/onboarding/` touches Cypher: the agents and the stage machine call this module, so the
graph stays the single source of truth and "close the browser and come back" works by construction.

Platform labels are `_`-prefixed (`_Tenant`, `_Session`, `_Message`, ...) so they can never collide with a
generated ontology label - `ripple.onboarding.validate` rejects any generated label starting with `_`.
"""

from __future__ import annotations

import json
from typing import Any

from ripple.db import TenantScope, new_id, now_ms
from ripple.graph.schema import apply_schema
from ripple.onboarding.models import (
    AgentStep,
    Brief,
    ChecklistItem,
    ChecklistOp,
    ExpertRole,
    FormAnswer,
    FormSpec,
    Message,
    OntologySpec,
)


def _j(value: Any) -> str:
    return json.dumps(value, default=str)


def _unj(text: Any, default: Any = None) -> Any:
    if text in (None, ""):
        return default
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return default


# --------------------------------------------------------------------------- tenant and session

def create_tenant(scope: TenantScope, name: str, industry: str = "") -> dict:
    """Create the tenant node and the platform indexes. Idempotent for one graph."""
    apply_schema(scope)
    row = {"id": scope.tenant_id, "name": name or scope.tenant_id, "industry": industry,
           "created_at": now_ms(), "stage": "interview", "status": "onboarding", "has_synthetic": False}
    scope.ops.run("tenant_upsert", {"row": row})
    return row


def get_tenant(scope: TenantScope) -> dict | None:
    rows = scope.ops.run("tenant_get", {})
    return rows[0] if rows else None


def set_tenant(scope: TenantScope, **patch) -> None:
    if patch:
        scope.ops.run("tenant_set", {"patch": patch})


def create_session(scope: TenantScope, provider: str, model: str) -> dict:
    sid = new_id("SES")
    row = {"id": sid, "stage": "interview", "started_at": now_ms(), "updated_at": now_ms(),
           "provider": provider, "model": model, "pending_json": ""}
    scope.ops.run("session_upsert", {"row": row})
    return row


def get_session(scope: TenantScope) -> dict | None:
    rows = scope.ops.run("session_get", {})
    return rows[0] if rows else None


def set_session(scope: TenantScope, sid: str, **patch) -> None:
    patch.setdefault("updated_at", now_ms())
    scope.ops.run("session_set", {"sid": sid, "patch": patch})


def set_pending(scope: TenantScope, sid: str, pending: dict | None) -> None:
    """Record the turn currently in flight, so a browser that closed mid-answer can re-issue it on resume."""
    set_session(scope, sid, pending_json=_j(pending) if pending else "")


def get_pending(scope: TenantScope) -> dict | None:
    s = get_session(scope)
    return _unj(s.get("pending_json") if s else None, None) or None


# --------------------------------------------------------------------------- messages

def append_message(scope: TenantScope, sid: str, msg: Message) -> Message:
    seq = scope.ops.run("message_max_seq", {"sid": sid})[0]["seq"] + 1
    m = msg.model_copy(update={"id": msg.id or new_id("MSG"), "ts": msg.ts or now_ms(), "seq": seq})
    row = {"id": m.id, "role": m.role, "agent": m.agent, "stage": m.stage, "kind": m.kind, "text": m.text,
           "payload_json": _j(m.payload), "ts": m.ts, "seq": m.seq}
    scope.ops.run("message_append", {"sid": sid, "row": row})
    return m


def list_messages(scope: TenantScope, sid: str, after: int = 0) -> list[Message]:
    out = []
    for r in scope.ops.run("messages_list", {"sid": sid, "after": after}):
        out.append(Message(id=r["id"], role=r["role"], agent=r["agent"] or "", stage=r["stage"], kind=r["kind"],
                           text=r["text"] or "", payload=_unj(r["payload_json"], {}) or {}, ts=r["ts"],
                           seq=r["seq"]))
    return out


# --------------------------------------------------------------------------- checklist

def apply_checklist_ops(scope: TenantScope, stage: str, ops: list[ChecklistOp]) -> list[ChecklistItem]:
    """Apply the agent's own checklist edits. Returns the stage's checklist afterwards."""
    existing = {c.id: c for c in list_checklist(scope, stage)}
    for op in ops:
        cid = op.id or new_id("CHK")
        cur = existing.get(cid)
        if op.op == "add" or cur is None:
            if not (op.question or (cur and cur.question)):
                continue
            item = ChecklistItem(id=cid, stage=stage, question=op.question or (cur.question if cur else ""),
                                 why=op.why, status="open", created_at=now_ms())
        elif op.op == "resolve":
            item = cur.model_copy(update={"status": "resolved", "resolved_at": now_ms(),
                                          "answer_summary": op.answer_summary or cur.answer_summary})
        elif op.op == "drop":
            item = cur.model_copy(update={"status": "dropped", "resolved_at": now_ms(),
                                          "answer_summary": op.answer_summary or cur.answer_summary})
        else:  # revise
            item = cur.model_copy(update={"question": op.question or cur.question, "why": op.why or cur.why})
        existing[cid] = item
        scope.ops.run("checklist_upsert", {"row": item.model_dump()})
    return list_checklist(scope, stage)


def list_checklist(scope: TenantScope, stage: str) -> list[ChecklistItem]:
    return [ChecklistItem.model_validate(r) for r in scope.ops.run("checklist_list", {"stage": stage})]


def open_checklist(scope: TenantScope, stage: str) -> list[ChecklistItem]:
    return [c for c in list_checklist(scope, stage) if c.status == "open"]


def reopen_item(scope: TenantScope, stage: str, question: str, why: str) -> ChecklistItem:
    item = ChecklistItem(id=new_id("CHK"), stage=stage, question=question, why=why, created_at=now_ms())
    scope.ops.run("checklist_upsert", {"row": item.model_dump()})
    return item


# --------------------------------------------------------------------------- attachments

def put_attachment(scope: TenantScope, row: dict) -> dict:
    row = {**row, "id": row.get("id") or new_id("ATT"), "ts": row.get("ts") or now_ms()}
    stored = {k: row.get(k, "") for k in ("id", "filename", "mime", "sha256", "kind", "text_path",
                                          "summary", "path")}
    stored["bytes"] = int(row.get("bytes") or 0)
    stored["ts"] = row["ts"]
    stored["profile_json"] = _j(row.get("profile") or {})
    scope.ops.run("attachment_upsert", {"row": stored})
    return row


def list_attachments(scope: TenantScope) -> list[dict]:
    out = []
    for r in scope.ops.run("attachments_list", {}):
        out.append({**r, "profile": _unj(r.pop("profile_json"), {})})
    return out


def get_attachment(scope: TenantScope, att_id: str) -> dict | None:
    rows = scope.ops.run("attachment_get", {"id": att_id})
    if not rows:
        return None
    r = rows[0]
    return {**r, "profile": _unj(r.pop("profile_json"), {})}


# --------------------------------------------------------------------------- brief

def put_brief(scope: TenantScope, brief: Brief, *, approved: bool = False,
              source_ids: list[str] | None = None) -> dict:
    """Store the brief. A new version is cut when the current one is already approved or has been flagged
    stale (which is what a jump back to stage 1 does); otherwise the open version is patched in place, since
    the interviewer edits it turn by turn."""
    cur = scope.ops.run("brief_current", {})
    row0 = cur[0] if cur else None
    if row0 and not (row0.get("approved") or row0.get("stale")):
        bid, version, created = row0["id"], row0["version"], row0["created_at"]
    else:
        version = (row0["version"] + 1) if row0 else 1
        bid, created = f"BRF-{version:03d}", now_ms()
    row = {"id": bid, "version": version, "json": _j(brief.model_dump()), "approved": approved, "stale": False,
           "created_at": created}
    scope.ops.run("brief_upsert", {"row": row})
    if source_ids:
        scope.ops.run("derived_from", {"id": bid, "source_ids": source_ids})
    return row


def current_brief(scope: TenantScope) -> tuple[Brief, dict] | tuple[None, None]:
    rows = scope.ops.run("brief_current", {})
    if not rows:
        return None, None
    return Brief.model_validate(_unj(rows[0]["json"], {}) or {}), rows[0]


def brief_versions(scope: TenantScope) -> list[dict]:
    return scope.ops.run("brief_versions", {})


# --------------------------------------------------------------------------- forms and answers

def save_form(scope: TenantScope, form: FormSpec) -> FormSpec:
    """Store a form round. A form with no id becomes the next round; one with an id is updated in place."""
    rounds = scope.ops.run("formspecs_list", {})
    known = {r["id"]: r for r in rounds}
    if form.id and form.id in known:
        f = form.model_copy(update={"round": known[form.id]["round"], "ts": form.ts or now_ms()})
    else:
        n = len(rounds) + 1
        f = form.model_copy(update={"id": form.id or f"FRM-{n:03d}", "round": n, "ts": form.ts or now_ms()})
    scope.ops.run("formspec_upsert", {"row": {
        "id": f.id, "round": f.round, "title": f.title, "intro": f.intro,
        "fields_json": _j([x.model_dump() for x in f.fields]), "status": f.status, "ts": f.ts}})
    return f


def get_form(scope: TenantScope, form_id: str) -> FormSpec | None:
    rows = scope.ops.run("formspec_get", {"id": form_id})
    return _row_to_form(rows[0]) if rows else None


def list_forms(scope: TenantScope) -> list[FormSpec]:
    return [_row_to_form(r) for r in scope.ops.run("formspecs_list", {})]


def open_form(scope: TenantScope) -> FormSpec | None:
    """The round the user is filling in. A stale one (the brief changed under it) no longer counts."""
    return next((f for f in reversed(list_forms(scope)) if f.status == "open" and not f.stale), None)


def _row_to_form(r: dict) -> FormSpec:
    return FormSpec(id=r["id"], round=r["round"], title=r["title"], intro=r["intro"] or "",
                    fields=_unj(r["fields_json"], []) or [], status=r["status"], stale=bool(r.get("stale")),
                    ts=r["ts"])


def set_form_status(scope: TenantScope, form_id: str, status: str) -> None:
    scope.ops.run("formspec_set_status", {"id": form_id, "status": status})


def save_answer(scope: TenantScope, ans: FormAnswer) -> FormAnswer:
    a = ans.model_copy(update={"id": ans.id or f"ANS-{ans.form_id}-{ans.field_id}", "ts": ans.ts or now_ms()})
    scope.ops.run("answer_upsert", {"row": {"id": a.id, "form_id": a.form_id, "field_id": a.field_id,
                                            "value_json": _j(a.value), "source": a.source,
                                            "confidence": a.confidence, "ts": a.ts}})
    return a


def list_answers(scope: TenantScope, form_id: str = "") -> list[FormAnswer]:
    out = []
    for r in scope.ops.run("answers_list", {"form_id": form_id}):
        out.append(FormAnswer(id=r["id"], form_id=r["form_id"], field_id=r["field_id"],
                              value=_unj(r["value_json"], None), source=r["source"],
                              confidence=r["confidence"], ts=r["ts"]))
    return out


# --------------------------------------------------------------------------- ontology spec

def save_spec(scope: TenantScope, spec: OntologySpec, *, status: str = "draft", rationale: str = "",
              source_ids: list[str] | None = None, new_version: bool = True) -> dict:
    cur = scope.ops.run("ontology_current", {})
    if cur and not new_version and cur[0]["status"] == "draft":
        oid, version = cur[0]["id"], cur[0]["version"]
    else:
        version = (cur[0]["version"] + 1) if cur else 1
        oid = f"ONT-{version:03d}"
    spec = spec.model_copy(update={"version": version})
    row = {"id": oid, "version": version, "json": _j(spec.model_dump(by_alias=True)), "status": status,
           "rationale": rationale or spec.rationale, "stale": False, "ts": now_ms()}
    scope.ops.run("ontology_upsert", {"row": row})
    types = [{"id": f"OTY-{oid}-{t.label}", "label": t.label, "description": t.description, "kind": "node"}
             for t in spec.types]
    types += [{"id": f"OTY-{oid}-{r.type}", "label": r.type, "description": r.description, "kind": "relationship"}
              for r in spec.relationships]
    if types:
        scope.ops.run("ontology_types_upsert", {"oid": oid, "rows": types})
    if source_ids:
        scope.ops.run("derived_from", {"id": oid, "source_ids": source_ids})
    return row


def current_spec(scope: TenantScope) -> tuple[OntologySpec, dict] | tuple[None, None]:
    rows = scope.ops.run("ontology_current", {})
    if not rows:
        return None, None
    return OntologySpec.model_validate(_unj(rows[0]["json"], {}) or {}), rows[0]


def approved_spec(scope: TenantScope) -> tuple[OntologySpec, dict] | tuple[None, None]:
    rows = scope.ops.run("ontology_approved", {})
    if not rows:
        return None, None
    return OntologySpec.model_validate(_unj(rows[0]["json"], {}) or {}), rows[0]


def set_spec_status(scope: TenantScope, spec_id: str, status: str) -> None:
    scope.ops.run("ontology_set_status", {"id": spec_id, "status": status})
    if status == "approved":
        scope.ops.run("ontology_supersede_others", {"id": spec_id})


def spec_versions(scope: TenantScope) -> list[dict]:
    return scope.ops.run("ontology_versions", {})


# --------------------------------------------------------------------------- experts

def save_expert(scope: TenantScope, role: ExpertRole) -> ExpertRole:
    r = role.model_copy(update={"id": role.id or f"EXP-{role.name}", "ts": role.ts or now_ms()})
    scope.ops.run("expert_upsert", {"row": {
        "id": r.id, "name": r.name, "title": r.title, "mandate": r.mandate, "justification": r.justification,
        "system_prompt": r.system_prompt, "tools_json": _j(r.tools),
        "focus_json": _j({"types": r.focus_types, "relationships": r.focus_relationships}),
        "playbook_json": _j(r.playbook), "status": r.status, "version": r.version, "origin": r.origin,
        "stale": r.stale, "ts": r.ts}})
    if r.focus_types:
        scope.ops.run("expert_focus_link", {"eid": r.id, "labels": r.focus_types})
    return r


def _row_to_expert(r: dict) -> ExpertRole:
    focus = _unj(r["focus_json"], {}) or {}
    return ExpertRole(id=r["id"], name=r["name"], title=r["title"] or "", mandate=r["mandate"] or "",
                      justification=r["justification"] or "", focus_types=focus.get("types") or [],
                      focus_relationships=focus.get("relationships") or [],
                      playbook=_unj(r["playbook_json"], []) or [], tools=_unj(r["tools_json"], []) or [],
                      system_prompt=r["system_prompt"] or "", status=r["status"], version=r["version"] or 1,
                      origin=r["origin"] or "generated", stale=bool(r.get("stale")), ts=r["ts"] or 0)


def list_experts(scope: TenantScope) -> list[ExpertRole]:
    return [_row_to_expert(r) for r in scope.ops.run("experts_list", {})]


def get_expert(scope: TenantScope, expert_id: str) -> ExpertRole | None:
    rows = scope.ops.run("expert_get", {"id": expert_id})
    return _row_to_expert(rows[0]) if rows else None


def set_expert_status(scope: TenantScope, expert_id: str, status: str) -> None:
    scope.ops.run("expert_set_status", {"id": expert_id, "status": status})


def delete_expert(scope: TenantScope, expert_id: str) -> None:
    scope.ops.run("expert_delete", {"id": expert_id})


# --------------------------------------------------------------------------- steps and staleness

def record_step(scope: TenantScope, step: AgentStep) -> AgentStep:
    s = step.model_copy(update={"id": step.id or new_id("STP"), "ts": step.ts or now_ms()})
    scope.ops.run("step_append", {"row": {"id": s.id, "stage": s.stage, "agent": s.agent, "kind": s.kind,
                                          "summary": s.summary[:1000], "payload_json": _j(s.payload),
                                          "ms": float(s.ms), "ts": s.ts}})
    return s


def step_count(scope: TenantScope, stage: str = "") -> int:
    return scope.ops.run("steps_count", {"stage": stage})[0]["n"]


def list_steps(scope: TenantScope, stage: str = "", limit: int = 200) -> list[dict]:
    """The newest `limit` steps, oldest first."""
    total = step_count(scope, stage)
    out = []
    for r in scope.ops.run("steps_list", {"stage": stage, "skip": max(0, total - limit), "limit": limit}):
        out.append({**r, "payload": _unj(r.pop("payload_json"), {})})
    return out


def mark_stale(scope: TenantScope, labels: list[str]) -> int:
    if not labels:
        return 0
    rows = scope.ops.run("artifacts_mark_stale", {"labels": labels})
    return rows[0]["flagged"] if rows else 0


def counts(scope: TenantScope) -> dict:
    rows = scope.ops.run("tenant_counts", {})
    return rows[0] if rows else {"nodes": 0, "edges": 0}


def instance_counts(scope: TenantScope) -> dict:
    nodes = {r["label"]: r["count"] for r in scope.ops.run("instance_counts", {})}
    edges = {r["rel"]: r["count"] for r in scope.ops.run("instance_edge_counts", {})}
    return {"nodes": nodes, "edges": edges}


def provenance_of(scope: TenantScope, node_id: str) -> list[dict]:
    return scope.ops.run("provenance_of", {"id": node_id})
