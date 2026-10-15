"""Score a recorded live run against eval/rubric.md with an LLM judge.

    .venv/bin/pytest -m llm -k full_onboarding -s        # writes artifacts/llm_runs/<ts>/
    .venv/bin/python eval/run_rubric.py                  # judges the newest run
    .venv/bin/python eval/run_rubric.py --run 20261015-204500

The judge gets the rubric, the run's artifacts and nothing else, and is told to quote rather than summarise.
Its scores are advisory: `rubric.json` carries a `human` block for the person who signs the run off, because
"an LLM said it was good" is not a result.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pydantic import BaseModel, Field  # noqa: E402

from ripple.llm.base import get_client  # noqa: E402
from ripple.llm.structured import ask_model  # noqa: E402

RUNS = ROOT / "artifacts" / "llm_runs"
RUBRIC = ROOT / "eval" / "rubric.md"
HONESTY = ("2.6", "3.7", "4.2", "4.6", "5.4")

SYSTEM = """You are judging a recorded run of a product called Ripple, which interviews a company and builds a
knowledge graph of its supply chain with four agents. You are given the run's artifacts and a rubric.

Score every item in sections 1 to 4 of the rubric as 0, 1 or 2. Section 5 needs a human at a browser: score an
item there only if the artifacts actually settle it, otherwise leave it out.

Rules:
- **Quote, do not summarise.** Every item's `evidence` must contain the exact words from the artifacts that
  decided the score. If you cannot find any, the score is 0 and the evidence says what was missing.
- Judge what is there, not what you would have written. A different but defensible choice scores 2.
- Be hard on the honesty items (2.6, 3.7, 4.2, 4.6): an invented value, a type the data cannot populate, a
  justification that names no ontology type, or an id that no tool returned is a 0, whatever else is good.
- `notes` is for what a human should look at first."""


class Item(BaseModel):
    id: str
    score: int = Field(ge=0, le=2)
    evidence: str


class Judgement(BaseModel):
    items: list[Item]
    notes: str = ""


def newest_run() -> Path:
    runs = [d for d in sorted(RUNS.iterdir()) if d.is_dir()] if RUNS.exists() else []
    if not runs:
        raise SystemExit(f"no runs in {RUNS}; run `.venv/bin/pytest -m llm -k full_onboarding -s` first")
    return runs[-1]


def artifacts(run: Path) -> dict:
    out: dict = {}
    for name in ("transcript", "brief", "ontology", "loaded", "experts", "expert_answers"):
        p = run / f"{name}.json"
        if p.exists():
            out[name] = json.loads(p.read_text())
    if not out:
        raise SystemExit(f"{run} holds no run artifacts")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", default="", help="a directory name under artifacts/llm_runs (default: the newest)")
    a = ap.parse_args()
    run = (RUNS / a.run) if a.run else newest_run()
    data = artifacts(run)
    body = json.dumps(data, default=str)[:400_000]
    out, reply = ask_model(get_client(), Judgement, SYSTEM, [{"role": "user", "content":
        f"# The rubric\n\n{RUBRIC.read_text()}\n\n# The run's artifacts\n\n```json\n{body}\n```\n\n"
        "Score it."}], effort="high")

    by_section: dict[str, list[Item]] = {}
    for item in out.items:
        by_section.setdefault(item.id.split(".")[0], []).append(item)
    total = sum(i.score for i in out.items)
    zeros = [i.id for i in out.items if i.score == 0]
    verdict = {
        "run": run.name,
        "model": reply.model,
        "total": total,
        "max_scored": 2 * len(out.items),
        "zeros": zeros,
        "honesty_failures": [z for z in zeros if z in HONESTY],
        "sections": {s: {"total": sum(i.score for i in items), "max": 2 * len(items)}
                     for s, items in sorted(by_section.items())},
        "items": [i.model_dump() for i in out.items],
        "notes": out.notes,
        "human": {"signed_off_by": "TODO(human)", "agrees_with_judge": None, "notes": ""},
    }
    (run / "rubric.json").write_text(json.dumps(verdict, indent=2) + "\n")
    print(f"{run.name}: {total}/{2 * len(out.items)} across {len(out.items)} items")
    for s, v in verdict["sections"].items():
        print(f"  section {s}: {v['total']}/{v['max']}")
    if verdict["honesty_failures"]:
        print(f"  HONESTY FAILURES: {verdict['honesty_failures']}")
    print(f"  notes: {out.notes[:300]}")
    print(f"wrote {(run / 'rubric.json').relative_to(ROOT)} - fill in its `human` block before quoting it")


if __name__ == "__main__":
    main()
