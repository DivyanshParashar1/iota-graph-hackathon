"""The generic expert agent: runs any generated role against its tenant's graph.

A role is data - a name, a mandate and a system prompt written by the expert generator - and this module is
the only code that runs it. The role's own prompt goes in as the system prompt; the host appends the ontology
and the tool contract, because those are facts about the runtime rather than about the role.

The tool set is deliberately the minimal read-only one (plan.md §4.4): enough to prove a generated role is
alive and answers from the real graph. What each role gets beyond that is decided with the main application.
"""

from __future__ import annotations

import json

from ripple.db import TenantScope
from ripple.llm.base import LLMClient, get_client
from ripple.llm.loop import run_tool_loop
from ripple.onboarding.models import ExpertRole
from ripple.onboarding.store import approved_spec, get_tenant
from ripple.tools.base import call_context
from ripple.tools.registry import READ_ONLY, TOOLS, call_tool, specs

HOST_RULES = """
## Your runtime

You answer questions about {company}'s supply chain by querying its knowledge graph through the tools below.
The graph was built for this company during onboarding, so its types are theirs, not a standard model.

- Call `describe_ontology` first in a new line of enquiry; do not assume a type or property exists.
- Every id in your answer must have come back from a tool in this conversation. Never invent one.
- Never invent a number. When the graph does not hold something, say so and say what would be needed.
- Properties carry a `confidence`: `ballpark` and `synthetic` values are not facts. Say when an answer rests
  on one.
- When a question is outside your mandate, say which role it belongs to instead of guessing.
- Answer in prose, under 200 words unless asked for more, and name the nodes you used.

## Your mandate

{mandate}

## The types you own

{focus}
"""


def role_tools(role: ExpertRole) -> list[str]:
    """The tools this role may use: its own list, intersected with what exists, defaulting to read-only."""
    wanted = [t for t in (role.tools or []) if t in TOOLS]
    return wanted or list(READ_ONLY)


def system_prompt(scope: TenantScope, role: ExpertRole) -> str:
    """The role's own prompt, plus the host contract and the ontology it reasons over."""
    tenant = get_tenant(scope) or {}
    spec, _ = approved_spec(scope)
    focus = ", ".join(role.focus_types) or "every type in the ontology"
    rules = HOST_RULES.format(company=tenant.get("name") or scope.tenant_id, mandate=role.mandate or role.title,
                              focus=focus)
    ontology = ""
    if spec:
        ontology = "\n## The ontology\n\n```json\n" + json.dumps(
            {"types": [{"label": t.label, "description": t.description,
                        "properties": [p.name for p in t.properties]} for t in spec.types],
             "relationships": [{"type": r.type, "from": r.from_, "to": r.to} for r in spec.relationships]},
            indent=2) + "\n```\n"
    return f"{role.system_prompt.strip()}\n{rules}{ontology}"


def ask(scope: TenantScope, role: ExpertRole, question: str, *, client: LLMClient | None = None,
        on_step=None, max_turns: int = 8) -> dict:
    """Run one role against one question. Returns {ok, text, turns, ids, steps, tools}."""
    client = client or get_client()
    names = role_tools(role)

    def call(name: str, args: dict):
        with call_context(agent=role.name):
            res = call_tool(scope, name, args)
        return {"summary": res.summary, "node_ids": res.node_ids, "data": res.data}

    out = run_tool_loop(client, system=system_prompt(scope, role), task=question, tools=specs(names),
                        call=call, on_step=on_step, max_turns=max_turns)
    return {**out, "tools": names, "role": role.name}
