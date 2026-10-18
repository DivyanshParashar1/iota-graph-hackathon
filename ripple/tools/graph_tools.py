"""Ontology-aware, tenant-generic graph tools: the minimal read-only set an expert role gets in M5.

These replace v1's DataCo-specific tools. None of them knows a label in advance - every one takes a label or
relationship type from the tenant's *approved* spec and is rejected if it names anything else, which is what
makes one tool set work for every generated ontology.

The richer tool set each role gets (write-back, algorithms, memory) is decided with the main application
(plan.md §10); these five are here so a generated expert can be asked a real question and answer it from the
tenant's real graph.
"""

from __future__ import annotations

from typing import Any

from ripple.db import TenantScope
from ripple.onboarding.models import OntologySpec
from ripple.onboarding.store import approved_spec, instance_counts
from ripple.tools.base import ToolError, ToolResult, logged_tool

MAX_LIMIT = 200


def _spec(scope: TenantScope) -> OntologySpec:
    spec, _ = approved_spec(scope)
    if spec is None:
        raise ToolError("this tenant has no approved ontology yet")
    return spec


def spec_type(scope: TenantScope, label: str):
    """A type of the approved spec by label; ToolError for anything else (so a label can reach Cypher)."""
    spec = _spec(scope)
    t = spec.type_map().get(label)
    if t is None:
        raise ToolError(f"unknown type {label!r}; this ontology has: {', '.join(sorted(spec.type_map()))}")
    return t


def title_property(t) -> str:
    """The property that names a node of this type: its display.title_property when declared, else id."""
    title = t.display.title_property or "name"
    return title if title == "id" or any(p.name == title for p in t.properties) else "id"


def _clamp(limit: Any, default: int = 25) -> int:
    try:
        return max(1, min(int(limit or default), MAX_LIMIT))
    except (TypeError, ValueError):
        return default


@logged_tool
def describe_ontology(scope: TenantScope) -> ToolResult:
    """The tenant's approved ontology: its types, their properties and the relationships between them."""
    spec = _spec(scope)
    counts = instance_counts(scope)
    types = [{"label": t.label, "description": t.description, "count": counts["nodes"].get(t.label, 0),
              "title_property": title_property(t),
              "properties": [{"name": p.name, "type": p.type, "unit": p.unit, "description": p.description}
                             for p in t.properties]} for t in spec.types]
    rels = [{"type": r.type, "from": r.from_, "to": r.to, "cardinality": r.cardinality,
             "count": counts["edges"].get(r.type, 0), "description": r.description,
             "properties": [p.name for p in r.properties]} for r in spec.relationships]
    return ToolResult({"version": spec.version, "types": types, "relationships": rels},
                      summary=f"{len(types)} types, {len(rels)} relationships")


@logged_tool
def find_nodes(scope: TenantScope, label: str, query: str = "", limit: int = 25) -> ToolResult:
    """Nodes of one type, optionally filtered by a substring of their title property or id."""
    t = spec_type(scope, label)
    n = _clamp(limit)
    prop = title_property(t)
    if query:
        rows = scope.ops.run("search_nodes", {"q": query, "limit": n}, label=label, prop=prop)
    else:
        rows = scope.ops.run("nodes_of_type", {"limit": n, "skip": 0}, label=label)
    data = [{"id": r["id"], **dict(r["properties"] or {})} for r in rows]
    return ToolResult({"label": label, "nodes": data}, node_ids=[r["id"] for r in rows],
                      queries=["search_nodes" if query else "nodes_of_type"],
                      summary=f"{len(data)} {label} node(s)" + (f" matching {query!r}" if query else ""))


@logged_tool
def get_node(scope: TenantScope, label: str, id: str) -> ToolResult:  # noqa: A002 - the graph calls it id
    """Every property of one node of a known type."""
    spec_type(scope, label)
    rows = scope.ops.run("node_lookup", {"id": id}, label=label)
    if not rows:
        raise ToolError(f"no {label} with id {id!r}")
    r = rows[0]
    return ToolResult({"id": r["id"], "labels": list(r["labels"] or []),
                       "properties": dict(r["properties"] or {})},
                      node_ids=[r["id"]], queries=["node_lookup"], summary=f"{label} {id}")


@logged_tool
def neighbours(scope: TenantScope, label: str, id: str, limit: int = 50) -> ToolResult:  # noqa: A002
    """One node's immediate neighbours, grouped by the relationship that reaches them."""
    spec_type(scope, label)
    rows = scope.ops.run("neighbourhood", {"id": id, "limit": _clamp(limit, 50)}, label=label)
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        key = f"{'->' if r['outgoing'] else '<-'}{r['rel']}"
        grouped.setdefault(key, []).append({"id": r["id"], "label": r["label"], "title": r["title"]})
    return ToolResult({"id": id, "neighbours": grouped}, node_ids=[id] + [r["id"] for r in rows],
                      edges=[(id, r["rel"], r["id"]) if r["outgoing"] else (r["id"], r["rel"], id)
                             for r in rows],
                      queries=["neighbourhood"], summary=f"{len(rows)} neighbour(s) of {id}")


@logged_tool
def aggregate(scope: TenantScope, label: str, property: str = "", group_by: str = "",  # noqa: A002
              limit: int = 25) -> ToolResult:
    """Count / sum / avg / min / max of a numeric property of a type, or counts grouped by a property."""
    t = spec_type(scope, label)
    names = {p.name for p in t.properties} | {"id"}
    if group_by:
        if group_by not in names:
            raise ToolError(f"{label} has no property {group_by!r}")
        rows = scope.ops.run("group_by_property", {"limit": _clamp(limit)}, label=label, prop=group_by)
        return ToolResult({"label": label, "group_by": group_by, "groups": rows}, queries=["group_by_property"],
                          summary=f"{label} grouped by {group_by}: {len(rows)} group(s)")
    if not property:
        raise ToolError("pass a property to aggregate, or a group_by")
    if property not in names:
        raise ToolError(f"{label} has no property {property!r}; it has: {', '.join(sorted(names))}")
    rows = scope.ops.run("aggregate_property", {}, label=label, prop=property)
    stats = rows[0] if rows else {}
    return ToolResult({"label": label, "property": property, **stats}, queries=["aggregate_property"],
                      summary=f"{label}.{property}: n={stats.get('count')} avg={stats.get('avg')}")


@logged_tool
def provenance(scope: TenantScope, id: str) -> ToolResult:  # noqa: A002
    """Where a node's values came from: the form answers and uploads behind it."""
    rows = scope.ops.run("provenance_of", {"id": id})
    return ToolResult({"id": id, "sources": rows}, node_ids=[id], queries=["provenance_of"],
                      summary=f"{len(rows)} source(s) for {id}")
