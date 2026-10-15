"""Source-fidelity eval: 20 brain questions with expected source documents (pass >= 18/20).

    python eval/run_brain_eval.py [--db PATH] [--sample 3000]
Builds a temporary DB (DataCo sample by default) unless --db points at a built one.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ripple.db import TenantScope, close_db, get_db  # noqa: E402
from ripple.tools.base import call_context  # noqa: E402
from ripple.tools.brain import ask  # noqa: E402


def run(scope: TenantScope, verbose: bool = True) -> dict:
    spec = yaml.safe_load((ROOT / "eval" / "brain_questions.yaml").read_text())
    n_top = spec.get("top_n", 3)
    rows = []
    with call_context(no_log=True):
        for q in spec["questions"]:
            r = ask(scope, question=q["question"]).data
            got = [s["doc_id"] for s in r["sources"]][:n_top]
            ok = any(e in got for e in q["expected"])
            intent_ok = q["intent"] in r["intent"]
            rows.append({**q, "got": got, "pass": ok, "intent_ok": intent_ok, "routed": r["intent"]})
            if verbose:
                print(f"{'PASS' if ok else 'FAIL'}  [{q['intent']:9}->{','.join(r['intent']):9}] {q['question'][:70]}"
                      + ("" if ok else f"\n      expected {q['expected']} got {got}"))
    passed = sum(r["pass"] for r in rows)
    return {"passed": passed, "total": len(rows), "intent_accuracy": sum(r["intent_ok"] for r in rows) / len(rows),
            "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--sample", type=int, default=3000)
    a = ap.parse_args()
    if a.db:
        db = get_db(a.db, mode="embedded")
    else:
        from ripple.ingest.build import build_tenant

        db = get_db(Path(tempfile.mkdtemp()) / "eval.db", mode="embedded")
        build_tenant(TenantScope("dataco", db), a.sample)
    res = run(TenantScope("dataco", db))
    print(f"\nbrain eval: {res['passed']}/{res['total']} cite an expected source (intent routing "
          f"{res['intent_accuracy']:.0%})")
    close_db(db)
    return 0 if res["passed"] >= 18 else 1


if __name__ == "__main__":
    raise SystemExit(main())
