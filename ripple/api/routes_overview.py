"""The overview API: the live company at a glance, for the home page once onboarding is done.

Nothing here knows a label. Hot spots are read off the tenant's *approved* spec: an enum property whose options
include a risky value ("delayed", "high", "overdue", ...) becomes a status hot spot, and a many-to-many link type
becomes a concentration check (how many objects depend on a single partner). Every label, property and
relationship comes from that spec and goes through the template queries' `ident` check.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends

from ripple.api.deps import scope_dep
from ripple.db import TenantScope
from ripple.incident.store import list_incidents
from ripple.onboarding import session as sess
from ripple.onboarding.store import approved_spec, get_tenant, instance_counts, list_experts
from ripple.tools.graph_tools import title_property

router = APIRouter(prefix="/api")

RISKY = re.compile(r"^(delayed|late|overdue|blocked|stuck|critical|high|very[ _-]?high|at[ _-]?risk|disrupted|"
                   r"shortage|short|failed|on[ _-]?hold|cancell?ed|exception|red|expired|suspended)$", re.I)
NEEDS_YOU = {"awaiting_approval"}
SAMPLE = 5


def _title(props: dict, prop: str, nid: str) -> str:
    return str(props.get(prop) or nid)


def status_hotspots(scope: TenantScope, spec) -> list[dict]:
    out = []
    for t in spec.types:
        prop_title = title_property(t)
        for p in t.properties:
            risky = [o for o in p.options if RISKY.match(o.strip())]
            if p.type != "enum" or not risky:
                continue
            counts = {r["value"]: r["count"] for r in scope.ops.run("group_by_property", {"limit": 50},
                                                                       label=t.label, prop=p.name)}
            total = sum(counts.values())
            for v in risky:
                n = counts.get(v, 0)
                if not n:
                    continue
                rows = scope.ops.run("nodes_with_value", {"value": v, "limit": SAMPLE}, label=t.label, prop=p.name)
                sample = [{"id": r["id"], "title": _title(dict(r["properties"] or {}), prop_title, r["id"])}
                          for r in rows]
                out.append({"kind": "status", "label": t.label, "property": p.name, "value": v, "count": n,
                            "total": total, "description": p.description, "sample": sample})
    return sorted(out, key=lambda h: -h["count"] / max(h["total"], 1))


def concentration_hotspots(scope: TenantScope, spec) -> list[dict]:
    types = spec.type_map()
    out = []
    for r in spec.relationships:
        if r.cardinality != "many-to-many" or r.from_ == r.to or r.to not in types:
            continue
        row = (scope.ops.run("single_linked_targets", {"limit": SAMPLE},
                             from_label=r.from_, rel=r.type, to_label=r.to) or [{}])[0]
        single, total = int(row.get("single") or 0), int(row.get("total") or 0)
        if not single:
            continue
        ids = list(row.get("sample_ids") or [])
        sample = scope.ops.run("nodes_by_ids", {"ids": ids}) if ids else []
        prop = title_property(types[r.to])
        out.append({"kind": "concentration", "rel": r.type, "from": r.from_, "to": r.to, "single": single,
                    "total": total, "description": r.description,
                    "sample": [{"id": s["id"], "title": _title(dict(s["properties"] or {}), prop, s["id"])}
                               for s in sample]})
    return sorted(out, key=lambda h: -h["single"] / max(h["total"], 1))


@router.get("/overview")
def overview(scope: TenantScope = Depends(scope_dep)):
    """Headline numbers, hot spots, incidents and experts for the live company."""
    tenant = get_tenant(scope) or {"id": scope.tenant_id}
    state = sess.state(scope)
    spec, _ = approved_spec(scope)
    counts = instance_counts(scope)
    incidents = list_incidents(scope, limit=50)
    by_status: dict[str, int] = {}
    for i in incidents:
        by_status[i.get("status") or "received"] = by_status.get(i.get("status") or "received", 0) + 1
    experts = [r for r in list_experts(scope) if r.status != "retired"]
    return {
        "tenant": {k: tenant.get(k) for k in ("id", "name", "industry", "stage", "status", "has_synthetic",
                                              "seeded_from")},
        "stage": state["stage"],
        "busy": state["busy"],
        "has_ontology": spec is not None,
        "version": spec.version if spec else None,
        "counts": counts,
        "types": len(spec.types) if spec else 0,
        "relationships": len(spec.relationships) if spec else 0,
        "hotspots": (status_hotspots(scope, spec) + concentration_hotspots(scope, spec)) if spec else [],
        "incidents": {"total": len(incidents), "by_status": by_status,
                      "needs_you": sum(1 for i in incidents if i.get("status") in NEEDS_YOU),
                      "recent": incidents[:6]},
        "experts": [{"id": r.id, "name": r.name, "title": r.title, "mandate": r.mandate, "status": r.status,
                     "focus_types": r.focus_types, "playbook": r.playbook[:2]} for r in experts],
    }
