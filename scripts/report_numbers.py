"""Measure every number the README quotes and write docs/numbers.md + docs/numbers.json.

    .venv/bin/python scripts/report_numbers.py              # deterministic only, ~1 minute
    .venv/bin/python scripts/report_numbers.py --with-llm   # also fold in the newest artifacts/llm_runs/

v2 has no dataset to build, so the measurements are about the platform rather than a corpus: how long the
deterministic suite takes, how fast a generated ontology is applied and loaded, what one tenant's graph costs,
and - when a live run has been recorded - what the four agents actually produced.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ripple.db import TenantScope, close_db, get_db  # noqa: E402
from ripple.graph.apply import apply_spec, load_instances  # noqa: E402
from ripple.graph.queries import all_queries  # noqa: E402
from ripple.onboarding import store  # noqa: E402
from ripple.onboarding.models import (  # noqa: E402
    InstanceBatch,
    InstanceEdge,
    InstanceNode,
    OntologySpec,
    PropertySpec,
    RelationshipSpec,
    TypeDisplay,
    TypeSpec,
)
from ripple.tools.registry import TOOLS, call_tool  # noqa: E402

OUT_MD = ROOT / "docs" / "numbers.md"
OUT_JSON = ROOT / "docs" / "numbers.json"
LLM_RUNS = ROOT / "artifacts" / "llm_runs"


def synthetic_spec(n_types: int = 12) -> OntologySpec:
    """A spec the size of a mid-sized manufacturer's, used only to time schema and loading."""
    types = [TypeSpec(label=f"Type{i}", description=f"type {i}", id_pattern=f"T{i}-####",
                      properties=[PropertySpec(name="name", type="string"),
                                  PropertySpec(name="country", type="string"),
                                  PropertySpec(name="value", type="float", unit="USD")],
                      display=TypeDisplay(title_property="name")) for i in range(n_types)]
    rels = [RelationshipSpec(type=f"REL_{i}", **{"from": f"Type{i}"}, to=f"Type{i + 1}",
                             properties=[PropertySpec(name="weight", type="float")])
            for i in range(n_types - 1)]
    return OntologySpec(version=1, types=types, relationships=rels, rationale="timing fixture")


def batch_for(spec: OntologySpec, per_type: int) -> InstanceBatch:
    nodes, edges = [], []
    for t in spec.types:
        for i in range(per_type):
            nodes.append(InstanceNode(label=t.label, id=f"{t.label}-{i:05d}",
                                      properties={"name": f"{t.label} {i}", "country": "CN",
                                                  "value": float(i)}))
    for r in spec.relationships:
        for i in range(per_type):
            edges.append(InstanceEdge(type=r.type, **{"from": f"{r.from_}-{i:05d}"},
                                      to=f"{r.to}-{i:05d}", properties={"weight": 1.0}))
    return InstanceBatch(nodes=nodes, edges=edges)


def timed(fn, *a, **kw):
    t0 = time.perf_counter()
    out = fn(*a, **kw)
    return out, round((time.perf_counter() - t0) * 1000, 1)


def measure_graph(per_type: int = 500) -> dict:
    d = Path(tempfile.mkdtemp())
    db = get_db(d / "numbers.db", mode="embedded")
    try:
        scope = TenantScope("numbers_run", db)
        _, t_tenant = timed(store.create_tenant, scope, "Numbers Run", "timing")
        spec = synthetic_spec()
        applied, t_apply = timed(apply_spec, scope, spec)
        store.set_spec_status(scope, store.save_spec(scope, spec)["id"], "approved")
        batch = batch_for(spec, per_type)
        loaded, t_load = timed(load_instances, scope, spec, batch)
        counts = store.instance_counts(scope)
        db.save()  # the .db file is only written on SAVE, and the README quotes its size
        tool_ms = {}
        for name, args in (("describe_ontology", {}), ("find_nodes", {"label": "Type0", "limit": 25}),
                           ("get_node", {"label": "Type0", "id": "Type0-00001"}),
                           ("neighbours", {"label": "Type0", "id": "Type0-00001"}),
                           ("aggregate", {"label": "Type0", "property": "value"})):
            runs = [timed(call_tool, scope, name, args)[1] for _ in range(20)]
            tool_ms[name] = {"p50": round(statistics.median(runs), 2),
                             "p95": round(sorted(runs)[int(0.95 * len(runs)) - 1], 2)}
        return {"tenant_create_ms": t_tenant, "apply_spec_ms": t_apply, "applied": applied,
                "load_instances_ms": t_load, "loaded": loaded,
                "nodes": sum(counts["nodes"].values()), "edges": sum(counts["edges"].values()),
                "nodes_per_second": round(loaded["nodes"] / (t_load / 1000), 1) if t_load else None,
                "db_bytes": (d / "numbers.db").stat().st_size if (d / "numbers.db").exists() else None,
                "tool_latency_ms": tool_ms}
    finally:
        close_db(db)


def measure_suite() -> dict:
    t0 = time.perf_counter()
    p = subprocess.run([str(ROOT / ".venv/bin/pytest"), "-q", "--no-header", "-p", "no:cacheprovider"],
                       capture_output=True, text=True, cwd=ROOT)
    secs = round(time.perf_counter() - t0, 1)
    tail = (p.stdout or "").strip().splitlines()[-1] if p.stdout else ""
    passed = next((int(w) for i, w in enumerate(tail.split()) if w.isdigit() and "pass" in tail), 0)
    return {"deterministic_tests": passed, "seconds": secs, "exit_code": p.returncode, "summary": tail}


def measure_counts() -> dict:
    qs = all_queries()
    tests = sorted((ROOT / "tests").glob("test_*.py"))
    prompts = sorted((ROOT / "ripple" / "onboarding" / "agents" / "prompts").glob("*.md"))
    py = sorted(ROOT.glob("ripple/**/*.py"))
    ts = sorted(ROOT.glob("ui/src/**/*.ts")) + sorted(ROOT.glob("ui/src/**/*.tsx"))
    return {
        "query_files": len(qs),
        "query_kinds": {k: sum(1 for q in qs.values() if q.kind == k) for k in {q.kind for q in qs.values()}},
        "tools": len(TOOLS),
        "prompt_files": len(prompts),
        "prompt_words": sum(len(p.read_text().split()) for p in prompts),
        "test_files": len(tests),
        "python_files": len(py),
        "python_lines": sum(len(p.read_text().splitlines()) for p in py),
        "ui_files": len(ts),
        "ui_lines": sum(len(p.read_text().splitlines()) for p in ts),
    }


def newest_llm_run() -> dict | None:
    if not LLM_RUNS.exists():
        return None
    runs = [d for d in sorted(LLM_RUNS.iterdir()) if d.is_dir() and (d / "brief.json").exists()]
    if not runs:
        return None
    d = runs[-1]
    def read(name: str):
        p = d / f"{name}.json"
        return json.loads(p.read_text()) if p.exists() else None

    brief, onto, loaded, experts = read("brief"), read("ontology"), read("loaded"), read("experts")
    transcript = read("transcript") or {}
    calls = len(list(d.glob("*-claude_code-*.json"))) + len(list(d.glob("*-openrouter-*.json")))
    return {
        "run": d.name,
        "llm_calls": calls,
        "interview_turns": len([t for t in transcript.get("turns", []) if t.get("user")]),
        "form_rounds": len([t for t in transcript.get("turns", []) if t.get("form")]),
        "brief_products": len((brief or {}).get("products") or []),
        "brief_suppliers": len((brief or {}).get("suppliers") or []),
        "ontology_types": len((onto or {}).get("types") or []),
        "ontology_relationships": len((onto or {}).get("relationships") or []),
        "nodes_loaded": (loaded or {}).get("counts", {}).get("nodes"),
        "experts": [{"name": e["name"], "focus": e["focus_types"], "prompt_words": len(e["system_prompt"].split())}
                    for e in (experts or [])],
    }


def to_markdown(data: dict) -> str:
    g, c, s = data["graph"], data["counts"], data["suite"]
    out = ["# Measured numbers", "",
           f"_Generated by `scripts/report_numbers.py` on {data['generated_at']} "
           f"({data['platform']['python']} on {data['platform']['machine']})._", "",
           "## The platform", "", "| | |", "|---|---|",
           f"| Query files (`graph/queries/*.cypher`) | {c['query_files']} |",
           f"| Tools in the registry | {c['tools']} |",
           f"| Agent prompts | {c['prompt_files']} files, {c['prompt_words']:,} words |",
           f"| Python | {c['python_files']} files, {c['python_lines']:,} lines |",
           f"| UI | {c['ui_files']} files, {c['ui_lines']:,} lines |",
           f"| Deterministic suite | {s['deterministic_tests']} tests in {s['seconds']}s |", "",
           "## One tenant's graph (12 generated types, 500 instances each)", "", "| | |", "|---|---|",
           f"| Tenant create + platform indexes | {g['tenant_create_ms']} ms |",
           f"| Apply the generated spec ({g['applied']['indexes_created']} indexes) | {g['apply_spec_ms']} ms |",
           f"| Load {g['loaded']['nodes']:,} nodes + {g['loaded']['edges']:,} edges | "
           f"{g['load_instances_ms']} ms ({g['nodes_per_second']:,.0f} nodes/s) |",
           f"| Graph on disk | {(g['db_bytes'] or 0) / 1e6:.1f} MB |", "",
           "### Tool latency (20 runs each)", "", "| Tool | p50 | p95 |", "|---|---|---|"]
    for name, lat in g["tool_latency_ms"].items():
        out.append(f"| `{name}` | {lat['p50']} ms | {lat['p95']} ms |")
    live = data.get("llm_run")
    if live:
        out += ["", "## The newest recorded live run", "",
                f"_`artifacts/llm_runs/{live['run']}`, provider calls: {live['llm_calls']}._", "",
                "| | |", "|---|---|",
                f"| Interview turns | {live['interview_turns']} |",
                f"| Form rounds | {live['form_rounds']} |",
                f"| Brief: products / suppliers | {live['brief_products']} / {live['brief_suppliers']} |",
                f"| Ontology: types / relationships | {live['ontology_types']} / "
                f"{live['ontology_relationships']} |",
                f"| Instance nodes loaded | {sum((live['nodes_loaded'] or {}).values()):,} |",
                f"| Expert roles generated | {len(live['experts'])} |", ""]
        if live["experts"]:
            out += ["| Role | Focus types | Prompt |", "|---|---|---|"]
            out += [f"| `{e['name']}` | {', '.join(e['focus'])} | {e['prompt_words']} words |"
                    for e in live["experts"]]
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--with-llm", action="store_true", help="fold in the newest artifacts/llm_runs/ summary")
    ap.add_argument("--skip-suite", action="store_true", help="do not run pytest")
    a = ap.parse_args()
    data = {
        "generated_at": time.strftime("%Y-%m-%d"),
        "platform": {"python": platform.python_version(), "machine": platform.machine(),
                     "system": platform.system()},
        "counts": measure_counts(),
        "graph": measure_graph(),
        "suite": {"deterministic_tests": 0, "seconds": 0.0, "exit_code": -1, "summary": "skipped"}
        if a.skip_suite else measure_suite(),
    }
    if a.with_llm:
        data["llm_run"] = newest_llm_run()
    OUT_JSON.write_text(json.dumps(data, indent=2) + "\n")
    OUT_MD.write_text(to_markdown(data))
    print(f"wrote {OUT_MD.relative_to(ROOT)} and {OUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
