"""Check Jev against documented human decisions. TypeSafe says its probabilities are calibrated (0.8 means right
about 80% of the time); this is how we check that on our own kind of decision rather than trusting it.

For each precedent: compile the decision as it stood at the time (`compile.precedent_request`), ask Jev, and
compare. A positive example agrees when Jev's top option is what the people chose; a negative example (the
choice that failed, like Ericsson's in 2000) agrees when Jev's top option is *not* it. Priority is compared
with `priority_in_hindsight`. Used by `eval/run_jev_precedents.py` and the `-m jev` live test.
"""

from __future__ import annotations

from ripple.decide import precedents as prec
from ripple.decide.compile import PRIORITY_QID, precedent_request
from ripple.decide.jev import DecisionModel, JevError


def evaluate(jev: DecisionModel, records: tuple[dict, ...] | None = None) -> dict:
    rows = []
    for r in records if records is not None else prec.load():
        req, labels = precedent_request(r)
        human = next((k for k, v in labels.items() if v == r["human_choice"]), None)
        try:
            res = jev.decide(req)
        except JevError as e:
            rows.append({"id": r["id"], "error": str(e)})
            continue
        dec, pr = res["decision"], res[PRIORITY_QID]
        negative = bool(r.get("is_negative_example"))
        agrees = (dec.top != human) if negative else (dec.top == human)
        rows.append({"id": r["id"], "negative": negative, "jev_choice": labels.get(dec.top, dec.top),
                     "p_jev_choice": round(dec.p(dec.top), 3), "p_human_choice": round(dec.p(human or ""), 3),
                     "agrees": agrees, "priority": pr.top, "p_priority": round(pr.p(pr.top), 3),
                     "priority_in_hindsight": r["priority_in_hindsight"],
                     "priority_agrees": pr.top == r["priority_in_hindsight"], "model": res.model, "ms": res.ms})
    ok = [x for x in rows if "error" not in x]
    return {"n": len(rows), "errors": len(rows) - len(ok),
            "agreement": round(sum(x["agrees"] for x in ok) / len(ok), 3) if ok else None,
            "priority_agreement": round(sum(x["priority_agrees"] for x in ok) / len(ok), 3) if ok else None,
            # calibration in miniature: mean confidence of the choices Jev got right vs wrong
            "mean_p_when_agrees": _mean([x["p_jev_choice"] for x in ok if x["agrees"]]),
            "mean_p_when_disagrees": _mean([x["p_jev_choice"] for x in ok if not x["agrees"]]),
            "rows": rows}


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 3) if xs else None
