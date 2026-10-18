"""The object explorer API: browse, search and open the instances of the approved ontology.

The UI's counterpart of the expert tools in `ripple/tools/graph_tools.py`, and it reuses their label check:
a type must be in the tenant's *approved* spec before its name reaches a Cypher template. Unlike the tools,
nothing here is logged as a tool call - browsing is not an agent step.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ripple.api.deps import scope_dep
from ripple.db import TenantScope
from ripple.onboarding.store import approved_spec, instance_counts, provenance_of
from ripple.tools.base import ToolError
from ripple.tools.graph_tools import spec_type, title_property

router = APIRouter(prefix="/api/objects")

MAX_LIMIT = 200


def _clamp(n: int, default: int = 50) -> int:
    return max(1, min(int(n or default), MAX_LIMIT))


def _type(scope: TenantScope, label: str):
    try:
        return spec_type(scope, label)
    except ToolError as e:
        raise HTTPException(404, str(e)) from e


def _row(r: dict, prop: str) -> dict:
    props = dict(r.get("properties") or {})
    return {"id": r["id"], "title": str(props.get(prop) or r["id"]), "properties": props}


@router.get("/search")
def search(q: str, limit: int = 5, scope: TenantScope = Depends(scope_dep)):
    """Objects of every approved type whose title or id contains `q`, a few per type."""
    spec, _ = approved_spec(scope)
    if spec is None or not q.strip():
        return {"q": q, "hits": []}
    n = max(1, min(limit, 20))
    hits = []
    for t in spec.types:
        prop = title_property(t)
        for r in scope.ops.run("search_nodes", {"q": q.strip(), "limit": n}, label=t.label, prop=prop):
            hits.append({"label": t.label, **_row(r, prop)})
    return {"q": q, "hits": hits}


@router.get("/{label}")
def list_objects(label: str, q: str = "", limit: int = 50, skip: int = 0, scope: TenantScope = Depends(scope_dep)):
    """One page of a type's objects, optionally filtered by a substring of the title property or id."""
    t = _type(scope, label)
    prop = title_property(t)
    n = _clamp(limit)
    if q.strip():
        rows = scope.ops.run("search_nodes", {"q": q.strip(), "limit": n}, label=label, prop=prop)
    else:
        rows = scope.ops.run("nodes_of_type", {"limit": n, "skip": max(0, skip)}, label=label)
    total = instance_counts(scope)["nodes"].get(label, 0)
    return {"label": label, "title_property": prop, "total": total, "skip": skip,
            "objects": [_row(r, prop) for r in rows]}


@router.get("/{label}/{node_id}")
def get_object(label: str, node_id: str, limit: int = 200, scope: TenantScope = Depends(scope_dep)):
    """One object with every property, its linked objects grouped by link type, and where it came from."""
    t = _type(scope, label)
    rows = scope.ops.run("node_lookup", {"id": node_id}, label=label)
    if not rows:
        raise HTTPException(404, f"no {label} with id {node_id!r}")
    prop = title_property(t)
    links: dict[tuple[str, str, str], list[dict]] = {}
    for r in scope.ops.run("neighbourhood", {"id": node_id, "limit": _clamp(limit, 200)}, label=label):
        key = (r["rel"], "out" if r["outgoing"] else "in", r["label"])
        links.setdefault(key, []).append({"id": r["id"], "label": r["label"], "title": r["title"]})
    return {
        "label": label,
        **_row(rows[0], prop),
        "links": [{"type": rel, "direction": d, "label": lbl, "objects": objs}
                  for (rel, d, lbl), objs in sorted(links.items())],
        "provenance": provenance_of(scope, node_id),
    }
