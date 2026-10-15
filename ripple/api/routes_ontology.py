"""The ontology API: inspect the spec, edit the draft by hand, ask the agent for a change, approve it.

Approval is the gate between "a diagram" and "a database": it validates, creates the indexes, extracts the
instance data from the data pack and loads it with provenance, then advances the stage.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ripple.api.deps import scope_dep
from ripple.db import TenantScope
from ripple.llm.base import LLMError, get_client
from ripple.onboarding import session as sess
from ripple.onboarding.agents import ontologist
from ripple.onboarding.events import StepEmitter
from ripple.onboarding.models import OntologySpec
from ripple.onboarding.store import (
    approved_spec,
    current_spec,
    get_session,
    instance_counts,
    provenance_of,
    save_spec,
    spec_versions,
)
from ripple.onboarding.validate import SpecInvalid, validate_spec

router = APIRouter(prefix="/api/ontology")


class DraftBody(BaseModel):
    spec: dict


@router.get("")
def get_ontology(scope: TenantScope = Depends(scope_dep)):
    """The current spec (draft or approved), its validation state, the diagram payload and instance counts."""
    spec, row = current_spec(scope)
    approved, approved_row = approved_spec(scope)
    return {"spec": spec.model_dump(by_alias=True) if spec else None, "row": row or {},
            "approved_version": (approved_row or {}).get("version"),
            "errors": validate_spec(spec) if spec else ["no spec yet"],
            "diagram": diagram(spec) if spec else {"nodes": [], "links": []},
            "versions": spec_versions(scope), "counts": instance_counts(scope),
            "has_approved": approved is not None}


def diagram(spec: OntologySpec) -> dict:
    """The force-graph payload: one node per type, one link per relationship."""
    return {
        "nodes": [{"id": t.label, "label": t.label, "description": t.description,
                   "properties": len(t.properties), "color": t.display.color or "",
                   "icon": t.display.icon or "", "tags": t.tags} for t in spec.types],
        "links": [{"source": r.from_, "target": r.to, "type": r.type, "cardinality": r.cardinality}
                  for r in spec.relationships],
    }


@router.patch("/draft")
def patch_draft(body: DraftBody, scope: TenantScope = Depends(scope_dep)):
    """Replace the draft with the user's edited spec. Validated, saved as a new version, never applied."""
    try:
        spec = OntologySpec.model_validate(body.spec)
    except Exception as e:  # noqa: BLE001 - pydantic errors are the useful message here
        raise HTTPException(400, f"that is not an ontology spec: {e}") from None
    errors = validate_spec(spec)
    if errors:
        raise HTTPException(400, {"message": "the edited spec is not valid", "errors": errors})
    row = save_spec(scope, spec, status="draft", rationale=spec.rationale, new_version=True)
    StepEmitter(scope, "ontology", "user")("write", f"spec v{row['version']} edited by hand")
    return get_ontology(scope)


@router.post("/approve")
def approve(scope: TenantScope = Depends(scope_dep)):
    """Validate, apply the indexes, load the instance data, advance to the experts stage."""
    s = get_session(scope)
    if not s:
        raise HTTPException(409, "no onboarding session")
    emit = StepEmitter(scope, "ontology", "ontologist")
    try:
        out = ontologist.approve(scope, s["id"], emit, client=get_client())
    except SpecInvalid as e:
        raise HTTPException(400, {"message": "the spec is not valid", "errors": e.errors}) from None
    except LLMError as e:
        raise HTTPException(503, str(e)) from None
    msgs = sess.advance(scope, s["id"], "ontology", reason="ontology approved")
    return {**out, "messages": [m.model_dump() for m in msgs], "state": sess.state(scope)}


@router.get("/provenance/{node_id}")
def node_provenance(node_id: str, scope: TenantScope = Depends(scope_dep)):
    """Where did this number come from? The answers and uploads behind one instance node."""
    return {"id": node_id, "sources": provenance_of(scope, node_id)}
