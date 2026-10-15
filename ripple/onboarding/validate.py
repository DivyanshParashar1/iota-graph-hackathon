"""Validation of a generated ontology spec, and of the instance data loaded against it.

Nothing reaches FalkorDB until it has been through here: the spec's labels and relationship types are
interpolated into Cypher (a per-tenant ontology cannot be parameterised), so this module is also the security
boundary that keeps a model-authored label from becoming Cypher. `ripple.graph.queries.ident` is the second
check, at the point of interpolation.
"""

from __future__ import annotations

import re

from ripple.onboarding.models import (
    CARDINALITIES,
    PROPERTY_TYPES,
    RESERVED_PREFIX,
    InstanceBatch,
    OntologySpec,
)

LABEL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
PROP_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class SpecInvalid(ValueError):
    """The spec cannot be applied. `errors` lists every problem, so the agent can fix them in one round."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_spec(spec: OntologySpec) -> list[str]:
    """Every problem with a spec, as readable messages. Empty list = the spec can be applied."""
    errors: list[str] = []
    labels: set[str] = set()
    for t in spec.types:
        if (t.label or "").startswith(RESERVED_PREFIX):
            errors.append(f"type label {t.label!r} uses the reserved '_' prefix")
            continue
        if not LABEL_RE.match(t.label or ""):
            errors.append(f"type label {t.label!r} is not a plain identifier")
            continue
        if t.label in labels:
            errors.append(f"duplicate type label {t.label!r}")
        labels.add(t.label)
        props = set()
        for p in t.properties:
            if not PROP_RE.match(p.name or ""):
                errors.append(f"{t.label}.{p.name!r} is not a snake_case property name")
                continue
            if p.name in props:
                errors.append(f"{t.label} declares {p.name!r} twice")
            props.add(p.name)
            if p.type not in PROPERTY_TYPES:
                errors.append(f"{t.label}.{p.name} has unknown type {p.type!r} "
                              f"(allowed: {', '.join(PROPERTY_TYPES)})")
            if p.type == "enum" and not p.options:
                errors.append(f"{t.label}.{p.name} is an enum with no options")
        title = t.display.title_property or "name"
        if title != "id" and title not in props:
            errors.append(f"{t.label}.display.title_property {title!r} is not one of its properties")
        if not t.id_pattern:
            errors.append(f"{t.label} has no id_pattern")

    patterns: dict[str, str] = {}
    for t in spec.types:
        if t.id_pattern:
            if t.id_pattern in patterns:
                errors.append(f"id_pattern {t.id_pattern!r} is used by both {patterns[t.id_pattern]} "
                              f"and {t.label}")
            patterns[t.id_pattern] = t.label

    rels: set[str] = set()
    for r in spec.relationships:
        if (r.type or "").startswith(RESERVED_PREFIX):
            errors.append(f"relationship type {r.type!r} uses the reserved '_' prefix")
            continue
        if not LABEL_RE.match(r.type or ""):
            errors.append(f"relationship type {r.type!r} is not a plain identifier")
            continue
        key = f"{r.type}:{r.from_}->{r.to}"
        if key in rels:
            errors.append(f"duplicate relationship {key}")
        rels.add(key)
        if r.from_ not in labels:
            errors.append(f"relationship {r.type} starts at unknown type {r.from_!r}")
        if r.to not in labels:
            errors.append(f"relationship {r.type} ends at unknown type {r.to!r}")
        if r.cardinality and r.cardinality not in CARDINALITIES:
            errors.append(f"relationship {r.type} has unknown cardinality {r.cardinality!r}")
        for p in r.properties:
            if not PROP_RE.match(p.name or ""):
                errors.append(f"{r.type}.{p.name!r} is not a snake_case property name")
            elif p.type not in PROPERTY_TYPES:
                errors.append(f"{r.type}.{p.name} has unknown type {p.type!r}")

    for ix in spec.indexes:
        if ix.label not in labels:
            errors.append(f"index on unknown type {ix.label!r}")
        elif ix.property != "id" and ix.property not in {p.name for t in spec.types if t.label == ix.label
                                                         for p in t.properties}:
            errors.append(f"index {ix.label}.{ix.property} is not a declared property")

    if not spec.types:
        errors.append("the spec declares no types")
    return errors


def require_valid(spec: OntologySpec) -> OntologySpec:
    errors = validate_spec(spec)
    if errors:
        raise SpecInvalid(errors)
    return spec


def validate_instances(spec: OntologySpec, batch: InstanceBatch) -> list[str]:
    """Problems with an instance batch against an approved spec (unknown labels, dangling edges, bad ids)."""
    errors: list[str] = []
    types = spec.type_map()
    rels = {r.type: r for r in spec.relationships}
    ids: dict[str, str] = {}
    for n in batch.nodes:
        if n.label not in types:
            errors.append(f"node {n.id!r} has unknown type {n.label!r}")
            continue
        if not n.id or not re.match(r"^[A-Za-z0-9][\w.:-]{0,127}$", n.id):
            errors.append(f"node id {n.id!r} of {n.label} is not usable as an id")
            continue
        if n.id in ids and ids[n.id] != n.label:
            errors.append(f"id {n.id!r} is used by both {ids[n.id]} and {n.label}")
        ids[n.id] = n.label
        declared = {p.name for p in types[n.label].properties} | {"id"}
        for k in n.properties:
            if not PROP_RE.match(k):
                errors.append(f"{n.label} {n.id}: property {k!r} is not a snake_case name")
            elif k not in declared:
                errors.append(f"{n.label} {n.id}: {k!r} is not declared on {n.label}")
    for e in batch.edges:
        r = rels.get(e.type)
        if r is None:
            errors.append(f"edge {e.type!r} is not in the spec")
            continue
        for side, nid in (("from", e.from_id), ("to", e.to_id)):
            if nid not in ids:
                errors.append(f"edge {e.type} {side} {nid!r} is not one of the nodes in this batch")
        if e.from_id in ids and ids[e.from_id] != r.from_:
            errors.append(f"edge {e.type} starts at {ids[e.from_id]}, the spec says {r.from_}")
        if e.to_id in ids and ids[e.to_id] != r.to:
            errors.append(f"edge {e.type} ends at {ids[e.to_id]}, the spec says {r.to}")
    return errors
