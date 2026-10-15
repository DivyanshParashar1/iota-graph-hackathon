"""Generate README.md from docs/README.template.md: ontology (graph/ontology.md), every query
(graph/queries/*.cypher headers + the key queries in full) and the measured numbers (docs/numbers.md).

    .venv/bin/python scripts/build_docs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ripple.graph.queries import all_queries  # noqa: E402
from ripple.ontology import to_markdown, write_markdown  # noqa: E402
from ripple.tools.registry import TOOLS  # noqa: E402

GROUPS = [
    ("Impact and blast radius", ("match_", "create_disruption", "open_incident", "incident_", "blast_", "impact_",
                                 "top_orders", "write_impacts", "set_incident", "revenue_at_risk", "customer_",
                                 "late_risk", "related_suppliers", "disruptions_active", "incidents_list")),
    ("Algorithms and routing", ("betweenness", "single_sourced", "supplier_downstream", "pagerank", "wcc", "cdlp",
                                "alt_route", "port_coords", "supplier_network_version", "lanes_get")),
    ("Sourcing and contracts", ("alt_suppliers", "contract_", "supplier_exposure", "suppliers_at_ports")),
    ("Actions (write-back)", ("nodes_exist", "propose_action", "link_evidence", "approve_action", "reject_action",
                              "claim_execution", "finish_execution", "action_", "actions_list", "orders_lanes",
                              "exec_", "undo_", "supplier_part_state", "create_reverse_action", "owners_for_entities")),
    ("Agents and coordination", ("handoff", "incident_handoffs", "log_tool_call")),
    ("Memory graph", ("upsert_playbook", "get_playbook", "playbooks_list", "record_episode", "playbook_outcome",
                      "episode", "fact_", "facts_", "log_conversation", "conversations_", "close_incident", "bump_risk")),
    ("Company brain", ("who_", "ownership_history", "team_backups", "suppliers_for_entity", "owner_sources",
                       "trace_decision", "decisions_all", "docs_", "doc_search", "doc_version", "delta_",
                       "handover_", "employees_list")),
    ("UI and API", ("map_", "meta_stats", "tenant_counts")),
    ("Ingest", ("load_", "link_")),
]
KEY = [("Q1", "blast_radius_port"), ("Q2", "blast_radius_supplier"), ("Q3", "single_sourced_parts"),
       ("Q4", "alt_suppliers"), ("Q5", "late_risk_baseline"), ("Q6", "who_owns"), ("Q7", "trace_decision"),
       ("Q8", "doc_search"), ("Q9", "action_get"), ("Q10a", "betweenness_suppliers"), ("Q10b", "pagerank_suppliers"),
       ("Q10c", "alt_route"), ("live", "revenue_at_risk"), ("action", "exec_reroute")]


def queries_md() -> str:
    qs = all_queries()
    out = ["### Key queries", ""]
    for qid, name in KEY:
        q = qs[name]
        out += [f"**{qid}. `{name}`**: {q.purpose}", "", "```cypher", q.text, "```", ""]
    out += [f"### All {len(qs)} query files", ""]
    placed: set[str] = set()
    for title, prefixes in GROUPS:
        names = [n for n in sorted(qs) if n not in placed and any(n.startswith(p) for p in prefixes)]
        if not names:
            continue
        placed |= set(names)
        body = ["| File | Kind | Graph | Purpose |", "|---|---|---|---|"]
        body += [f"| [`{n}`](graph/queries/{n}.cypher) | {qs[n].kind} | {qs[n].graph} | {qs[n].purpose.replace('|', '/')} |"
                 for n in names]
        if title == "Ingest":
            out += [f"<details><summary>{title} ({len(names)} files)</summary>", ""] + body + ["", "</details>", ""]
        else:
            out += [f"#### {title}", ""] + body + [""]
    rest = [n for n in sorted(qs) if n not in placed]
    if rest:
        out += ["#### Other", "", "| File | Kind | Purpose |", "|---|---|---|"]
        out += [f"| [`{n}`](graph/queries/{n}.cypher) | {qs[n].kind} | {qs[n].purpose} |" for n in rest]
    return "\n".join(out)


def strip_h1(md: str) -> str:
    lines = md.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip().replace("\n## ", "\n### ")


def main() -> None:
    write_markdown()
    tpl = (ROOT / "docs" / "README.template.md").read_text()
    numbers = ROOT / "docs" / "numbers.md"
    out = (tpl.replace("{{ONTOLOGY}}", strip_h1(to_markdown()))
              .replace("{{QUERIES}}", queries_md())
              .replace("{{NUMBERS}}", strip_h1(numbers.read_text()) if numbers.exists() else "_Run scripts/report_numbers.py._")
              .replace("{{N_TOOLS}}", str(len(TOOLS))))
    (ROOT / "README.md").write_text(out)
    print(f"wrote README.md ({len(out.splitlines())} lines)")


if __name__ == "__main__":
    main()
