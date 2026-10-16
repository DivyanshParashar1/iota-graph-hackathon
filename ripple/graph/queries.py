"""Loads every product Cypher query from graph/queries/*.cypher.

Each file starts with a header of `// key: value` comment lines:

    // name: messages_list
    // purpose: Every message of a session in order
    // graph: ops            (ops | mem)
    // kind: read            (read | write | algo | template)
    // params: {"sid": "SES-example"}

The README's query section is generated from these headers, so code and docs can't drift apart.

**Templates.** A per-tenant ontology is generated at runtime, and Cypher cannot parameterise a label or a
relationship type. Those queries are `kind: template` and carry `{placeholders}` which `Q(name, label=...)`
fills in. Every placeholder value is checked against `IDENT_RE` first, so only identifiers the ontology
validator already accepted can reach the query text.
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
IDENT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")


class BadIdentifier(ValueError):
    """A template placeholder was not a plain Cypher identifier."""


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
    return QueryDef(
        name=meta.get("name", path.stem),
        purpose=meta.get("purpose", ""),
        text="\n".join(body).strip(),
        graph=meta.get("graph", "ops"),
        kind=meta.get("kind", "read"),
        params=json.loads(meta["params"]) if meta.get("params") else {},
        path=path,
    )


@lru_cache
def all_queries() -> dict[str, QueryDef]:
    return {p.stem: _parse(p) for p in sorted(QUERY_DIR.glob("*.cypher"))}


def ident(value: str) -> str:
    """A label / relationship type / property name safe to interpolate into Cypher."""
    if not IDENT_RE.match(str(value or "")):
        raise BadIdentifier(f"{value!r} is not a plain identifier")
    return str(value)


def Q(name: str, **fmt) -> str:
    """The text of a named query; keyword arguments fill a template's {placeholders} (as identifiers)."""
    try:
        text = all_queries()[name].text
    except KeyError:
        raise KeyError(f"no query graph/queries/{name}.cypher") from None
    if not fmt:
        return text
    return text.format(**{k: ident(v) for k, v in fmt.items()})


def query_def(name: str) -> QueryDef:
    return all_queries()[name]
