"""How experienced people decided in real disruptions: `precedents.jsonl`, one documented case per line.

Jev cannot be trained (closed weights, zero-shot over the criteria it is given), so human judgement reaches it
two ways: the heuristics below go into every choice question's instructions, and the nearest precedents go
into its state. The same file is the calibration set (`eval/run_jev_precedents.py`): compile each case into a
Jev request and check that Jev favours the choice that worked.

Selection is deterministic retrieval (token overlap on kind and summary), not a decision.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

PRECEDENTS_FILE = Path(__file__).parent / "precedents.jsonl"
REQUIRED = ("id", "event", "known_at_decision", "actor", "options_considered", "human_choice", "outcome",
            "priority_in_hindsight", "heuristics")
PRIORITIES = ("low", "medium", "high", "critical")

# The decision heuristics the precedents support, keyed as they are in the file's `heuristics` lists.
HEURISTICS = {
    "escalate_on_weak_signals": "Escalate on weak signals; do not anchor on the affected party's first, "
                                "optimistic estimate of the damage.",
    "secure_scarce_capacity_first": "Secure scarce capacity, stock or allocation before competitors do: it "
                                    "goes to whoever asks first.",
    "prefer_reversible_under_uncertainty": "While the duration is uncertain, prefer reversible actions; commit to "
                                           "irreversible ones when the expected disruption outlasts their cost.",
    "use_prequalified_alternatives": "Use pre-qualified alternatives (another site, port, warehouse or supplier "
                                     "already in the network) before new ones.",
    "help_source_recover_when_no_alternative": "When there is no alternative source, help the disrupted source "
                                               "recover.",
    "protect_most_exposed_customers_and_notify_early": "Protect the customers who would suffer most, and tell "
                                                       "affected parties early.",
}
_STOP = {"a", "an", "the", "of", "at", "in", "on", "to", "and", "or", "for", "with", "by", "is", "was", "its",
         "from", "as", "be", "may", "no", "not", "this", "that", "until", "further", "notice"}
_WORD = re.compile(r"[a-z]+")


@lru_cache
def load(path: str | None = None) -> tuple[dict, ...]:
    p = Path(path) if path else PRECEDENTS_FILE
    return tuple(json.loads(line) for line in p.read_text().splitlines() if line.strip())


def problems(records: tuple[dict, ...] | list[dict]) -> list[str]:
    """What is wrong with the precedent file: missing fields, unknown heuristics, a choice not among the options."""
    errs: list[str] = []
    seen: set[str] = set()
    for r in records:
        who = r.get("id", "<no id>")
        for k in REQUIRED:
            if k not in r:
                errs.append(f"{who}: missing {k}")
        if who in seen:
            errs.append(f"{who}: duplicate id")
        seen.add(who)
        if r.get("human_choice") not in (r.get("options_considered") or []):
            errs.append(f"{who}: human_choice is not one of options_considered")
        if len(r.get("options_considered") or []) < 2:
            errs.append(f"{who}: fewer than two options considered")
        if r.get("priority_in_hindsight") not in PRIORITIES:
            errs.append(f"{who}: priority_in_hindsight must be one of {PRIORITIES}")
        unknown = [h for h in r.get("heuristics") or [] if h not in HEURISTICS]
        if unknown:
            errs.append(f"{who}: unknown heuristics {unknown}")
    return errs


def _tokens(text: str) -> set[str]:
    words = _WORD.findall((text or "").lower().replace("_", " "))
    return {w for w in words if w not in _STOP and len(w) > 2}


def _text(r: dict) -> str:
    ev = r.get("event") or {}
    return f"{ev.get('kind', '')} {ev.get('summary', '')}"


def nearest(kind: str, summary: str, k: int = 3, records: tuple[dict, ...] | None = None) -> list[dict]:
    """The k precedents whose kind and summary overlap the event most. A positive/negative pair about the same
    event (Nokia and Ericsson) is kept together, so the contrast reaches Jev - which can make the list one longer
    than k."""
    recs = records if records is not None else load()
    q = _tokens(f"{kind} {summary}")
    if not q:
        return []
    scored = []
    for r in recs:
        t = _tokens(_text(r))
        kind_bonus = 0.5 if (r.get("event") or {}).get("kind") == kind else 0.0
        score = len(q & t) / max(1, len(q | t)) + kind_bonus
        if score > 0:
            scored.append((score, r["id"], r))
    scored.sort(key=lambda x: (-x[0], x[1]))
    out: list[dict] = []
    for _, _, r in scored:
        if r in out:
            continue
        out.append(r)
        date = (r.get("event") or {}).get("date")
        for twin in recs:  # the same event seen from another actor
            if twin is not r and (twin.get("event") or {}).get("date") == date and twin not in out \
                    and twin.get("event", {}).get("kind") == r.get("event", {}).get("kind"):
                out.append(twin)
        if len(out) >= k:
            break
    return out


def render(r: dict) -> str:
    ev = r.get("event") or {}
    known = r.get("known_at_decision") or {}
    known_s = "; ".join(f"{k.replace('_', ' ')}: {v if not isinstance(v, list) else ', '.join(map(str, v))}"
                        for k, v in known.items())
    verdict = "This did NOT work." if r.get("is_negative_example") else "This worked."
    return (f"- {ev.get('date', '')} | {r.get('actor', '')} | {ev.get('summary', '')}\n"
            f"  Known when deciding: {known_s}\n"
            f"  Options: {' / '.join(r.get('options_considered') or [])}\n"
            f"  Chose: {r.get('human_choice', '')} (decided in {r.get('time_to_decide', 'n/a')})\n"
            f"  Outcome: {r.get('outcome', '')} {verdict}")


def heuristics_text() -> str:
    return "\n".join(f"- {h}" for h in HEURISTICS.values())
