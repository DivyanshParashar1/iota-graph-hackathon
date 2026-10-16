"""Applies graph/schema_platform.cypher idempotently to a tenant's ops and mem graphs.

The platform schema only covers the `_`-prefixed labels. Indexes for a tenant's *generated* ontology are
created by `ripple.graph.apply.apply_spec` when the user approves the spec.
"""

from __future__ import annotations

from ripple import ROOT
from ripple.db import TenantScope

SCHEMA_FILE = ROOT / "graph" / "schema_platform.cypher"


def schema_statements() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"ops": [], "mem": []}
    target = "ops"
    for line in SCHEMA_FILE.read_text().splitlines():
        s = line.strip()
        if s.startswith("// graph:"):
            target = s.split(":", 1)[1].strip()
        elif s and not s.startswith("//"):
            out[target].append(s)
    return out


def exists_error(e: Exception) -> bool:
    msg = str(e).lower()
    return "already" in msg or "exists" in msg


def apply_schema(scope: TenantScope) -> int:
    """Create every platform index; 'already indexed' errors are ignored. Returns the number created."""
    created = 0
    for gname, stmts in schema_statements().items():
        g = scope.ops if gname == "ops" else scope.mem
        for st in stmts:
            try:
                g.raw(st)
                created += 1
            except Exception as e:
                if exists_error(e):
                    continue
                raise
    return created
