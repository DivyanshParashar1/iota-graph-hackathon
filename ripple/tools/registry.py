"""TOOLS: name -> ToolSpec(fn, JSON schema, kind, description). The expert runtime, the API and tests all read
this. Schemas never include a tenant: the tenant comes from the session/scope."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ripple.tools import graph_tools
from ripple.tools.base import ToolError, ToolResult

READ_ONLY = ("describe_ontology", "find_nodes", "get_node", "neighbours", "aggregate", "provenance")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    fn: Callable[..., ToolResult]
    kind: str  # read | write | algo
    description: str
    schema: dict

    def spec(self) -> dict:
        """The tool as the LLM layer wants it."""
        return {"name": self.name, "description": self.description, "input_schema": self.schema}


def S(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or [], "additionalProperties": False}


STR = {"type": "string"}
INT = {"type": "integer"}
LABEL = {"type": "string", "description": "A node type from this tenant's approved ontology."}

_DEFS = [
    (graph_tools.describe_ontology, "read",
     "This tenant's approved ontology: node types with their properties and instance counts, and the "
     "relationships between them. Call this first - the ontology is different for every company.", S({})),
    (graph_tools.find_nodes, "read",
     "Nodes of one type, optionally filtered by a substring of their title property or id.",
     S({"label": LABEL, "query": STR, "limit": INT}, ["label"])),
    (graph_tools.get_node, "read", "Every property of one node, by type and id.",
     S({"label": LABEL, "id": STR}, ["label", "id"])),
    (graph_tools.neighbours, "read",
     "One node's immediate neighbours, grouped by the relationship that reaches them and its direction.",
     S({"label": LABEL, "id": STR, "limit": INT}, ["label", "id"])),
    (graph_tools.aggregate, "read",
     "count/sum/avg/min/max of a numeric property of a type, or node counts grouped by a property.",
     S({"label": LABEL, "property": STR, "group_by": STR, "limit": INT}, ["label"])),
    (graph_tools.provenance, "read",
     "Where a node's values came from: the onboarding form answers and uploaded files behind it.",
     S({"id": STR}, ["id"])),
]

TOOLS: dict[str, ToolSpec] = {fn.__name__: ToolSpec(fn.__name__, fn, kind, desc, schema)
                              for fn, kind, desc, schema in _DEFS}


def specs(names: list[str] | None = None) -> list[dict]:
    """Tool specs for the LLM layer, in registry order; unknown names are ignored."""
    wanted = list(names) if names else list(TOOLS)
    return [TOOLS[n].spec() for n in wanted if n in TOOLS]


def call_tool(scope, name: str, args: dict) -> ToolResult:
    spec = TOOLS.get(name)
    if spec is None:
        raise KeyError(f"unknown tool {name}")
    allowed = set(spec.schema["properties"])
    bad = set(args) - allowed
    if bad:
        raise ToolError(f"unexpected arguments for {name}: {sorted(bad)}")
    return spec.fn(scope, **args)
