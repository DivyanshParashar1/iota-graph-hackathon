"""Generate README.md from docs/README.template.md.

    .venv/bin/python scripts/report_numbers.py && .venv/bin/python scripts/build_docs.py

Placeholders the template may use:
  {{QUERIES}}   every graph/queries/*.cypher file, grouped, with the key ones in full
  {{PROMPTS}}   the four agent prompts, with a word count and their opening lines
  {{MODELS}}    the artifact models (the contract between the agents, the graph and the UI)
  {{TOOLS}}     the tool registry
  {{NUMBERS}}   docs/numbers.md
  {{N_TOOLS}} {{N_QUERIES}} {{N_TESTS}}
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ripple.graph.queries import all_queries  # noqa: E402
from ripple.onboarding.agents.common import PROMPT_DIR  # noqa: E402
from ripple.tools.registry import TOOLS  # noqa: E402

GROUPS = [
    ("Onboarding state", ("tenant_", "session_", "message_", "checklist_", "attachment_", "step_", "steps_")),
    ("Artifacts and versioning", ("brief_", "formspec", "answer", "answers_", "ontology_", "expert_",
                                  "experts_", "artifacts_", "derived_from")),
    ("The generated ontology (templates)", ("instance_", "node_lookup", "nodes_of_type", "neighbourhood",
                                            "aggregate_", "group_by_", "search_nodes", "provenance_")),
    ("Platform", ("meta_stats", "tool_call", "tool_calls")),
]
KEY = [
    ("resume", "messages_list"),
    ("the stage cursor", "session_get"),
    ("artifact history", "ontology_versions"),
    ("staleness", "artifacts_mark_stale"),
    ("loading a generated type", "instance_merge_nodes"),
    ("loading a generated relationship", "instance_merge_edges"),
    ("where did this come from", "provenance_of"),
    ("one node's neighbourhood", "neighbourhood"),
]


def queries_md() -> str:
    qs = all_queries()
    out = ["### Key queries", ""]
    for label, name in KEY:
        q = qs[name]
        kind = " (template: `{...}` is filled from the approved spec)" if q.kind == "template" else ""
        out += [f"**{name}** — {label}{kind}: {q.purpose}", "", "```cypher", q.text, "```", ""]
    out += [f"### All {len(qs)} query files", ""]
    placed: set[str] = set()
    for title, prefixes in GROUPS:
        names = [n for n in sorted(qs) if n not in placed and any(n.startswith(p) for p in prefixes)]
        if not names:
            continue
        placed |= set(names)
        out += [f"#### {title}", "", "| File | Kind | Graph | Purpose |", "|---|---|---|---|"]
        out += [f"| [`{n}`](graph/queries/{n}.cypher) | {qs[n].kind} | {qs[n].graph} | "
                f"{qs[n].purpose.replace('|', '/')} |" for n in names]
        out += [""]
    rest = [n for n in sorted(qs) if n not in placed]
    if rest:
        out += ["#### Other", "", "| File | Kind | Purpose |", "|---|---|---|"]
        out += [f"| [`{n}`](graph/queries/{n}.cypher) | {qs[n].kind} | {qs[n].purpose} |" for n in rest]
    return "\n".join(out)


def prompts_md() -> str:
    out = ["| Prompt | Words | Opens with |", "|---|---|---|"]
    for p in sorted(PROMPT_DIR.glob("*.md")):
        text = p.read_text().strip()
        first = next((ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")), "")
        rel = p.relative_to(ROOT)
        out.append(f"| [`{p.stem}`]({rel}) | {len(text.split()):,} | {first[:120].replace('**', '')} |")
    return "\n".join(out)


def tools_md() -> str:
    out = ["| Tool | Kind | What it does |", "|---|---|---|"]
    for name, spec in TOOLS.items():
        out.append(f"| `{name}` | {spec.kind} | {spec.description.splitlines()[0]} |")
    return "\n".join(out)


def models_md() -> str:
    import inspect

    from ripple.onboarding import models

    rows = ["| Model | Produced by | Fields |", "|---|---|---|"]
    who = {"Brief": "the interviewer", "InterviewTurn": "the interviewer", "FormSpec": "the data agent",
           "DataTurn": "the data agent", "FormAnswer": "the user (or Synthesize)",
           "OntologySpec": "the ontology agent", "OntologyTurn": "the ontology agent",
           "InstanceBatch": "the ontology agent", "ExpertRole": "the expert generator (or the user)",
           "ExpertsTurn": "the expert generator"}
    for name in ("Brief", "InterviewTurn", "FormSpec", "DataTurn", "FormAnswer", "OntologySpec",
                 "OntologyTurn", "InstanceBatch", "ExpertRole", "ExpertsTurn"):
        cls = getattr(models, name)
        fields = ", ".join(f"`{f}`" for f in cls.model_fields)
        rows.append(f"| [`{name}`](ripple/onboarding/models.py#L{inspect.getsourcelines(cls)[1]}) | "
                    f"{who.get(name, '')} | {fields} |")
    return "\n".join(rows)


def strip_h1(md: str) -> str:
    lines = md.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip().replace("\n## ", "\n### ")


def n_tests() -> int:
    import re

    total = 0
    for p in (ROOT / "tests").glob("test_*.py"):
        total += len(re.findall(r"^def test_", p.read_text(), re.M))
    return total


def main() -> None:
    tpl = (ROOT / "docs" / "README.template.md").read_text()
    numbers = ROOT / "docs" / "numbers.md"
    out = (tpl.replace("{{QUERIES}}", queries_md())
              .replace("{{PROMPTS}}", prompts_md())
              .replace("{{TOOLS}}", tools_md())
              .replace("{{MODELS}}", models_md())
              .replace("{{NUMBERS}}", strip_h1(numbers.read_text()) if numbers.exists()
                       else "_Run scripts/report_numbers.py._")
              .replace("{{N_TOOLS}}", str(len(TOOLS)))
              .replace("{{N_QUERIES}}", str(len(all_queries())))
              .replace("{{N_TESTS}}", str(n_tests())))
    (ROOT / "README.md").write_text(out)
    print(f"wrote README.md ({len(out.splitlines())} lines)")


if __name__ == "__main__":
    main()
