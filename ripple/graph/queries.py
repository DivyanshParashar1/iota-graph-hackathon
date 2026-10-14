"""Loads every product Cypher query from graph/queries/*.cypher.

Each file starts with a header of `// key: value` comment lines:

    // name: blast_radius_port
    // purpose: Q1. Open orders, revenue and customers hit by a port closure
    // graph: ops            (ops | mem)
    // kind: read            (read | algo | write)
    // params: {"did": "DIS-example"}

The README's query section is generated from these headers, so code and docs can't drift apart.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ripple import ROOT

QUERY_DIR = ROOT / "graph" / "queries"
_HEADER = re.compile(r"^//\s*(\w+):\s*(.*)$")


@dataclass(frozen=True)
class QueryDef:
    name: str
    purpose: str
    text: str
    graph: str = "ops"
    kind: str = "read"
    params: dict = field(default_factory=dict)
    path: Path | None = None


def _parse(path: Path) -> QueryDef:
    meta: dict[str, str] = {}
    body: list[str] = []
    for line in path.read_text().splitlines():
        m = _HEADER.match(line.strip())
        if m and not body:
            meta[m.group(1)] = m.group(2).strip()
        elif line.strip().startswith("//") and not body:
            continue
        else:
            body.append(line)
    text = "\n".join(body).strip()
    return QueryDef(
        name=meta.get("name", path.stem),
        purpose=meta.get("purpose", ""),
        text=text,
        graph=meta.get("graph", "ops"),
        kind=meta.get("kind", "read"),
        params=json.loads(meta["params"]) if meta.get("params") else {},
        path=path,
    )


@lru_cache
def all_queries() -> dict[str, QueryDef]:
    return {p.stem: _parse(p) for p in sorted(QUERY_DIR.glob("*.cypher"))}


def Q(name: str) -> str:  # noqa: N802 - short on purpose: Q("blast_radius_port")
    try:
        return all_queries()[name].text
    except KeyError:
        raise KeyError(f"no query graph/queries/{name}.cypher") from None


def query_def(name: str) -> QueryDef:
    return all_queries()[name]
