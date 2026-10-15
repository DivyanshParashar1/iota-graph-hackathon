"""Applies an approved OntologySpec to a tenant graph: indexes first, then the instance data with provenance.

Labels and relationship types come from a model, so they are interpolated into Cypher - which is why nothing
here runs before `ripple.onboarding.validate.require_valid` has passed. Every query is still a file in
`graph/queries/*.cypher` (`kind: template`), and `GraphHandle.run(..., label=...)` fills the placeholders
through `ripple.graph.queries.ident`, which is the single point where a model-authored string can reach Cypher.
"""

from __future__ import annotations

from typing import Any

from ripple.db import TenantScope, now_ms
from ripple.graph.schema import exists_error
from ripple.onboarding.models import InstanceBatch, OntologySpec
from ripple.onboarding.validate import require_valid, validate_instances

BATCH = 2000


def apply_spec(scope: TenantScope, spec: OntologySpec) -> dict:
    """Create the spec's indexes (every type's id, plus the declared ones). Idempotent."""
    require_valid(spec)
    wanted: list[tuple[str, str]] = [(t.label, "id") for t in spec.types]
    wanted += [(ix.label, ix.property) for ix in spec.indexes]
    for t in spec.types:
        title = t.display.title_property or "name"
        if title != "id" and any(p.name == title for p in t.properties):
            wanted.append((t.label, title))
    created, skipped = 0, 0
    for label, prop in dict.fromkeys(wanted):
        try:
            scope.ops.run("create_index", {}, label=label, prop=prop)
            created += 1
        except Exception as e:  # noqa: BLE001
            if exists_error(e):
                skipped += 1
                continue
            raise
    return {"indexes_created": created, "indexes_existing": skipped, "types": len(spec.types),
            "relationships": len(spec.relationships)}


def _flat(props: dict[str, Any]) -> dict[str, Any]:
    """FalkorDB rejects map-valued properties: flatten one level and JSON-encode anything deeper."""
    import json

    out: dict[str, Any] = {}
    for k, v in props.items():
        if isinstance(v, dict):
            for ik, iv in v.items():
                if isinstance(iv, (str, int, float, bool)) or iv is None:
                    out[f"{k}_{ik}"] = iv
                else:
                    out[f"{k}_{ik}"] = json.dumps(iv, default=str)
        elif isinstance(v, (list, tuple)):
            prim = [x for x in v if isinstance(x, (str, int, float, bool))]
            out[k] = prim if len(prim) == len(v) else json.dumps(list(v), default=str)
        else:
            out[k] = v
    return out


def load_instances(scope: TenantScope, spec: OntologySpec, batch: InstanceBatch, *,
                   wipe: bool = False) -> dict:
    """Write an instance batch as nodes and edges of the approved types, with provenance back to its sources."""
    require_valid(spec)
    errors = validate_instances(spec, batch)
    if errors:
        from ripple.onboarding.validate import SpecInvalid

        raise SpecInvalid(errors)
    if wipe:
        scope.ops.run("instance_wipe", {})
        scope.ops.run("provenance_wipe", {})

    by_label: dict[str, list[dict]] = {}
    prov: list[dict] = []
    for n in batch.nodes:
        row = {"id": n.id, **_flat(n.properties)}
        row.setdefault("confidence", n.confidence)
        by_label.setdefault(n.label, []).append(row)
        for sid in n.source_ids:
            prov.append({"node_id": n.id, "source_id": sid, "source": "user", "confidence": n.confidence,
                         "ts": now_ms()})
    nodes = 0
    for label, rows in by_label.items():
        for i in range(0, len(rows), BATCH):
            res = scope.ops.run("instance_merge_nodes", {"rows": rows[i:i + BATCH]}, label=label)
            nodes += res[0]["merged"] if res else 0

    # Grouped by (relationship, endpoint labels) so the MATCHes hit the id index of a known label rather
    # than scanning every node: without the labels this is the slowest step in the whole load.
    rel_of = {r.type: r for r in spec.relationships}
    label_of = {n.id: n.label for n in batch.nodes}
    by_rel: dict[tuple[str, str, str], list[dict]] = {}
    for e in batch.edges:
        r = rel_of[e.type]
        key = (e.type, label_of.get(e.from_id, r.from_), label_of.get(e.to_id, r.to))
        by_rel.setdefault(key, []).append({"from": e.from_id, "to": e.to_id, "props": _flat(e.properties)})
    edges = 0
    for (rel, from_label, to_label), rows in by_rel.items():
        for i in range(0, len(rows), BATCH):
            res = scope.ops.run("instance_merge_edges", {"rows": rows[i:i + BATCH]}, rel=rel,
                                from_label=from_label, to_label=to_label)
            edges += res[0]["merged"] if res else 0

    links = 0
    for i in range(0, len(prov), BATCH):
        res = scope.ops.run("provenance_link", {"rows": prov[i:i + BATCH]})
        links += res[0]["links"] if res else 0
    return {"nodes": nodes, "edges": edges, "provenance": links}
