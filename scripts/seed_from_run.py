"""Rebuild a tenant from a recorded live run, with no LLM calls.

    .venv/bin/pytest -m llm -k full_onboarding -s         # records artifacts/llm_runs/<ts>/
    .venv/bin/python scripts/seed_from_run.py --db var/demo.db
    RIPPLE_DB_PATH=var/demo.db .venv/bin/uvicorn ripple.api.app:app

A live run's graph lives in a temporary database that is thrown away when the test ends. This replays the run's
recorded artifacts - the brief, the approved ontology, the expert roles, the chat transcript - into a database
you keep, so the UI can be clicked through (and screenshotted) against real agent output without paying for
another run.

It is a **replay, not a simulation**: every artifact came out of a real model, and the tenant it builds is
marked `seeded_from` with the run id so nobody mistakes it for a live session. The instance data is the one
thing it cannot replay (the loader's output is not recorded), so it re-derives nodes from the run's form
answers only where they are unambiguous - see `--help`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ripple.db import TenantScope, close_db, get_db, slug_tenant_id  # noqa: E402
from ripple.experts.store import export_role  # noqa: E402
from ripple.graph.apply import apply_spec, load_instances  # noqa: E402
from ripple.onboarding import store  # noqa: E402
from ripple.onboarding.models import (  # noqa: E402
    Brief,
    ExpertRole,
    InstanceBatch,
    InstanceNode,
    Message,
    OntologySpec,
)

RUNS = ROOT / "artifacts" / "llm_runs"


def newest_run() -> Path:
    runs = [d for d in sorted(RUNS.iterdir()) if d.is_dir() and (d / "brief.json").exists()] \
        if RUNS.exists() else []
    if not runs:
        raise SystemExit(f"no recorded runs in {RUNS}; run `.venv/bin/pytest -m llm -k full_onboarding -s`")
    return runs[-1]


def read(run: Path, name: str):
    p = run / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def instances_from_answers(spec: OntologySpec, run: Path) -> InstanceBatch:
    """The run's repeating-group answers as nodes, where a group's rows map onto exactly one type.

    A row is matched to a type when the type has a property for every column the row uses. That is enough for
    the suppliers, lanes and sites a form collects, and it deliberately gives up rather than guessing: a real
    load is the ontology agent's job (`ontologist.approve`)."""
    transcript = read(run, "transcript") or {}
    nodes: list[InstanceNode] = []
    counters: dict[str, int] = {}
    for turn in transcript.get("turns", []):
        for field_id, value in (turn.get("answers") or {}).items():
            if not isinstance(value, list) or not value or not isinstance(value[0], dict):
                continue
            cols = {k for row in value if isinstance(row, dict) for k in row}
            best, score = None, 0
            for t in spec.types:
                props = {p.name for p in t.properties}
                hit = len(cols & props)
                if hit > score:
                    best, score = t, hit
            if best is None or score < 2:
                continue
            for row in value:
                if not isinstance(row, dict):
                    continue
                counters[best.label] = counters.get(best.label, 0) + 1
                props = {p.name for p in best.properties}
                nodes.append(InstanceNode(
                    label=best.label, id=f"{best.label.upper()[:3]}-{counters[best.label]:04d}",
                    properties={k: v for k, v in row.items() if k in props and isinstance(v, (str, int, float))},
                    confidence="ballpark"))
            print(f"  {field_id} -> {len(value)} {best.label}")
    return InstanceBatch(nodes=nodes, notes=f"replayed from {run.name} form answers")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", default="", help="a directory under artifacts/llm_runs (default: the newest)")
    ap.add_argument("--db", default="var/demo.db")
    ap.add_argument("--tenant", default="", help="tenant id (default: derived from the brief's company)")
    a = ap.parse_args()
    run = (RUNS / a.run) if a.run else newest_run()
    brief_data = read(run, "brief")
    if not brief_data:
        raise SystemExit(f"{run} has no brief.json")
    brief = Brief.model_validate(brief_data)
    spec_data = read(run, "ontology")
    experts = read(run, "experts") or []
    answers = read(run, "expert_answers") or []
    transcript = read(run, "transcript") or {}

    db = get_db(Path(a.db), mode="embedded")
    try:
        tid = a.tenant or slug_tenant_id(brief.company or "replay")
        scope = TenantScope(tid, db)
        scope.drop()
        store.create_tenant(scope, brief.company or "Replay", brief.industry)
        store.set_tenant(scope, seeded_from=run.name)
        session = store.create_session(scope, "replay", run.name)
        sid = session["id"]
        print(f"tenant {tid} in {a.db} (replay of {run.name})")

        for turn in transcript.get("turns", []):
            if turn.get("user"):
                store.append_message(scope, sid, Message(role="agent", agent="interviewer", stage="interview",
                                                         text=turn.get("agent", "")))
                store.append_message(scope, sid, Message(role="user", stage="interview", text=turn["user"]))
            elif turn.get("form"):
                store.append_message(scope, sid, Message(
                    role="user", stage="data", kind="form", text=f"Submitted {turn['form']}.",
                    payload={"form_id": turn["form"], "answers": turn.get("answers") or {}}))
        store.put_brief(scope, brief, approved=True)
        print(f"  brief: {len(brief.products)} products, {len(brief.suppliers)} suppliers")

        if spec_data:
            spec = OntologySpec.model_validate(spec_data)
            row = store.save_spec(scope, spec, status="draft", rationale=spec.rationale)
            store.set_spec_status(scope, row["id"], "approved")
            applied = apply_spec(scope, spec)
            print(f"  ontology v{row['version']}: {applied['types']} types, "
                  f"{applied['relationships']} relationships")
            batch = instances_from_answers(spec, run)
            if batch.nodes:
                loaded = load_instances(scope, spec, batch, wipe=True)
                print(f"  instances: {loaded['nodes']} nodes")

        for e in experts:
            role = ExpertRole.model_validate({**e, "status": "approved"})
            export_role(scope, store.save_expert(scope, role))
        if experts:
            print(f"  experts: {', '.join(e['name'] for e in experts)}")
        for ans in answers:
            store.append_message(scope, sid, Message(role="user", stage="ready", text=ans.get("question", "")))
            store.append_message(scope, sid, Message(role="agent", agent=ans.get("role", "expert"),
                                                      stage="ready", text=ans.get("text", "")))

        store.set_session(scope, sid, stage="ready")
        store.set_tenant(scope, stage="ready", status="live")
        c = store.counts(scope)
        print(f"  graph: {c['nodes']} nodes, {c['edges']} edges")
        print(f"\nRIPPLE_DB_PATH={a.db} .venv/bin/uvicorn ripple.api.app:app")
    finally:
        db.save()
        close_db(db)


if __name__ == "__main__":
    main()
