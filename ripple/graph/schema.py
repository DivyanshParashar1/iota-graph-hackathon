"""Applies graph/schema.cypher idempotently to a tenant's ops and mem graphs."""

from __future__ import annotations

from ripple import ROOT
from ripple.db import TenantScope

SCHEMA_FILE = ROOT / "graph" / "schema.cypher"


def schema_statements(dim: int = 384) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"ops": [], "mem": []}
    target = "ops"
    for line in SCHEMA_FILE.read_text().splitlines():
        s = line.strip()
        if s.startswith("// graph:"):
            target = s.split(":", 1)[1].strip()
        elif s and not s.startswith("//"):
            out[target].append(s.replace("{dim}", str(dim)))
    return out


def apply_schema(scope: TenantScope, dim: int | None = None) -> int:
    """Create every index; 'already indexed' errors are ignored. Returns the number of new indexes."""
    if dim is None:
        from ripple.embed import get_embedder

        dim = get_embedder().dim
    created = 0
    for gname, stmts in schema_statements(dim).items():
        g = scope.ops if gname == "ops" else scope.mem
        for st in stmts:
            try:
                g.raw(st)
                created += 1
            except Exception as e:  # noqa: BLE001
                msg = str(e).lower()
                if "already" in msg or "exists" in msg:
                    continue
                raise
    return created
