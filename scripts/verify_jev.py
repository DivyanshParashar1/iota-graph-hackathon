"""Make one real Jev call with the worked scenario and print exactly what comes back.

    .venv/bin/python scripts/verify_jev.py --dry-run     # print the compiled request; no network
    .venv/bin/python scripts/verify_jev.py               # call Jev (JEV_API_KEY or OPENROUTER_API_KEY)
    .venv/bin/python scripts/verify_jev.py --base-url https://api.typesafe.ai/v1 --model jev-1.13.0

The response field names are the one thing about Jev the build could not verify (docs/m8_decision_pipeline.md
§3). Run this once, then write the raw body into reference/JEV_VERIFIED.md and narrow
`ripple.decide.jev.parse_response` to that shape. Both the raw body and the parsed answers are saved to
artifacts/jev_runs/verify-<ts>.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from ripple.config import get_settings  # noqa: E402
from ripple.decide import precedents as prec  # noqa: E402
from ripple.decide.compile import decision_request  # noqa: E402
from ripple.decide.jev import JevError, parse_response  # noqa: E402
from ripple.incident.models import DecisionPacket  # noqa: E402

SCENARIO = ROOT / "eval" / "decisions" / "scenario_felixstowe_fire.json"


def main() -> int:
    s = get_settings()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="print the request and stop")
    ap.add_argument("--base-url", default=s.jev_base_url)
    ap.add_argument("--model", default=s.jev_model)
    args = ap.parse_args()

    packet = DecisionPacket.model_validate(json.loads(SCENARIO.read_text())["decision_packet"])
    req, qmap = decision_request(packet, prec.nearest(packet.event.kind, packet.event.summary), model=args.model)
    body = req.body(args.model)
    problems = req.problems()
    if args.dry_run:
        print(json.dumps(body, indent=2))
        print(f"\n# question map: {json.dumps(qmap.to_dict())}", file=sys.stderr)
        print(f"# problems: {problems or 'none'}", file=sys.stderr)
        return 0 if not problems else 1
    if problems:
        print(f"the request is invalid: {problems}", file=sys.stderr)
        return 1
    if not s.jev_key:
        print("no key: set JEV_API_KEY or OPENROUTER_API_KEY", file=sys.stderr)
        return 1
    url = f"{args.base_url.rstrip('/')}/systemone"
    t0 = time.perf_counter()
    r = httpx.post(url, json=body, timeout=s.jev_timeout,
                   headers={"Authorization": f"Bearer {s.jev_key}", "X-Title": "Ripple"})
    ms = round((time.perf_counter() - t0) * 1000)
    print(f"POST {url} -> HTTP {r.status_code} in {ms} ms\n")
    try:
        raw = r.json()
    except ValueError:
        print(r.text)
        return 1
    print(json.dumps(raw, indent=2))
    out = {"url": url, "status": r.status_code, "ms": ms, "request": body, "raw": raw}
    try:
        res = parse_response(raw, req)
        out["parsed"] = {k: a.model_dump() for k, a in res.answers.items()}
        print("\nparsed:")
        for k, a in res.answers.items():
            print(f"  {k}: top={a.top} p={a.p(a.top):.3f} {dict(a.ranked()[:4])}")
    except JevError as e:
        out["parse_error"] = str(e)
        print(f"\nthe parser could not read this body: {e}", file=sys.stderr)
    d = ROOT / "artifacts" / "jev_runs"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"verify-{time.strftime('%Y%m%d-%H%M%S')}.json"
    p.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nsaved {p.relative_to(ROOT)}")
    return 0 if r.status_code < 400 and "parse_error" not in out else 1


if __name__ == "__main__":
    raise SystemExit(main())
