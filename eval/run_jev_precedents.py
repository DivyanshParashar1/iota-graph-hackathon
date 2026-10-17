"""Ask Jev every documented precedent and report how often it agrees with what worked.

    .venv/bin/python eval/run_jev_precedents.py            # needs JEV_API_KEY or OPENROUTER_API_KEY
    .venv/bin/python eval/run_jev_precedents.py --json     # the full result as JSON

Each case is compiled as the decision stood at the time (no outcome, no choice) by
`ripple.decide.compile.precedent_request`; `ripple.decide.calibrate.evaluate` does the scoring. Results land in
artifacts/jev_runs/precedents-<ts>.json. The heuristics Jev is given were distilled from these same cases, so
treat agreement as an upper bound; add held-out cases to ripple/decide/precedents.jsonl for an honest number.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ripple.decide import calibrate  # noqa: E402
from ripple.decide.jev import JevError, get_jev_client  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    try:
        jev = get_jev_client()
    except JevError as e:
        print(e, file=sys.stderr)
        return 1
    out = calibrate.evaluate(jev)
    d = ROOT / "artifacts" / "jev_runs"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"precedents-{time.strftime('%Y%m%d-%H%M%S')}.json"
    p.write_text(json.dumps(out, indent=2))
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    for r in out["rows"]:
        if "error" in r:
            print(f"{r['id']:<40} ERROR {r['error']}")
            continue
        mark = "agrees " if r["agrees"] else "DIFFERS"
        neg = " (negative example)" if r["negative"] else ""
        print(f"{r['id']:<40} {mark} p={r['p_jev_choice']:.2f} priority {r['priority']}"
              f"/{r['priority_in_hindsight']}{neg}\n    jev: {r['jev_choice']}")
    print(f"\nagreement {out['agreement']}  priority agreement {out['priority_agreement']}  "
          f"mean p when agreeing {out['mean_p_when_agrees']} / disagreeing {out['mean_p_when_disagrees']}  "
          f"errors {out['errors']}/{out['n']}\nsaved {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
