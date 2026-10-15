"""Company brain: ask (answer contract) and delta ingest; memory inspector; algorithm panels."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ripple.api.deps import scope_dep, tool_error
from ripple.db import TenantScope
from ripple.ingest.delta import ingest_delta
from ripple.ingest.synth import SYNTH_DIR
from ripple.tools.algos import single_points_of_failure, supplier_clusters, supplier_influence
from ripple.tools.base import ToolError
from ripple.tools.brain import ask
from ripple.tools.memory import conversations

router = APIRouter(prefix="/api")


class AskIn(BaseModel):
    question: str
    user_id: str = "USR-demo"
    conversation_id: str | None = None
    incident_id: str | None = None
    mode: str = "scripted"


class IngestIn(BaseModel):
    kind: str = "chat"
    text: str
    author_id: str | None = None
    channel: str = "#general"
    title: str | None = None
    doc_id: str | None = None


@router.post("/brain/ask")
def brain_ask(body: AskIn, scope: TenantScope = Depends(scope_dep)):
    try:
        return ask(scope, question=body.question, user_id=body.user_id, conversation_id=body.conversation_id,
                   incident_id=body.incident_id, mode=body.mode).data
    except ToolError as e:
        raise tool_error(e) from e


@router.post("/brain/ingest")
def brain_ingest(body: IngestIn, scope: TenantScope = Depends(scope_dep)):
    try:
        return ingest_delta(scope, kind=body.kind, text=body.text, author_id=body.author_id, channel=body.channel,
                            title=body.title, doc_id=body.doc_id).data
    except ToolError as e:
        raise tool_error(e) from e


@router.get("/brain/handover-sample")
def handover_sample(scope: TenantScope = Depends(scope_dep)):
    p = SYNTH_DIR / scope.tenant_id / "delta" / "handover.json"
    return json.loads(p.read_text()) if p.exists() else {}


@router.get("/people")
def people(scope: TenantScope = Depends(scope_dep)):
    return scope.ops.run("employees_list", {})


@router.get("/memory/episodes")
def episodes(scope: TenantScope = Depends(scope_dep)):
    return scope.mem.run("episodes_all", {})


@router.get("/memory/playbooks")
def playbooks(scope: TenantScope = Depends(scope_dep)):
    return scope.mem.run("playbooks_list", {})


@router.get("/memory/facts")
def facts(subject_id: str | None = None, history: bool = True, scope: TenantScope = Depends(scope_dep)):
    if subject_id:
        return scope.mem.run("facts_about", {"s": subject_id, "history": history})
    rows = scope.mem.run("facts_recent", {"limit": 200})
    return rows if history else [r for r in rows if r["invalid_at"] is None]


@router.get("/memory/conversations")
def convs(user_id: str | None = None, scope: TenantScope = Depends(scope_dep)):
    if user_id:
        return conversations(scope, user_id)
    return scope.mem.run("conversations_all", {})


@router.get("/algos/spof")
def spof(top_k: int = 10, scope: TenantScope = Depends(scope_dep)):
    return single_points_of_failure(scope, top_k=top_k).to_dict()


@router.get("/algos/influence")
def influence(top_k: int = 10, scope: TenantScope = Depends(scope_dep)):
    return supplier_influence(scope, top_k=top_k).to_dict()


@router.get("/algos/clusters")
def clusters(scope: TenantScope = Depends(scope_dep)):
    return supplier_clusters(scope).to_dict()
