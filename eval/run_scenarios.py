"""Agents vs ground truth: run the full orchestrator on every scenario and compare the Incident's numbers and
IMPACTS edges with eval/ground_truth.py (pandas). Exits non-zero on any mismatch.

    python eval/run_scenarios.py [--sample 3000 | --full] [--db PATH]
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from ground_truth import ground_truth  # noqa: E402

from ripple.agents.orchestrator import Orchestrator  # noqa: E402
from ripple.db import TenantScope, close_db, get_db  # noqa: E402
from ripple.scenarios import load_scenarios, scenario_event  # noqa: E402
from ripple.tools.impact import get_incident  # noqa: E402


def run(db, sample_ids: list[int] | None, verbose: bool = True) -> dict:
    s = TenantScope("dataco", db)
    rows = []
    for sid in load_scenarios():
        gt = ground_truth(sid, "dataco", sample_ids)
        t0 = time.time()
        iid = Orchestrator(s, "scripted").run(scenario_event(sid, "dataco"))
        wall = round(time.time() - t0, 2)
        inc = get_incident(s, iid)["incident"]
        impacted = sorted(r["id"] for r in s.ops.query(
            "MATCH (:Incident {id: $iid})-[:IMPACTS]->(o:Order) RETURN o.id AS id", {"iid": iid}))
        ok = (impacted == gt["order_ids"] and inc["orders_at_risk_initial"] == gt["orders"]
              and abs(inc["revenue_at_risk_initial"] - gt["revenue"]) < 0.01
              and inc["customers_affected"] == gt["customers"])
        rows.append({"scenario": sid, "incident": iid, "orders": inc["orders_at_risk_initial"], "gt_orders": gt["orders"],
                     "revenue": round(inc["revenue_at_risk_initial"], 2), "gt_revenue": gt["revenue"],
                     "customers": inc["customers_affected"], "gt_customers": gt["customers"], "exact": ok,
                     "wall_s": wall})
        if verbose:
            print(f"{'EXACT' if ok else 'MISMATCH':8} {sid:26} orders {inc['orders_at_risk_initial']:6d}/{gt['orders']:<6d} "
                  f"revenue ${inc['revenue_at_risk_initial']:,.2f} / ${gt['revenue']:,.2f}  agents {wall}s")
    return {"rows": rows, "exact": sum(r["exact"] for r in rows), "total": len(rows)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=3000)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--db", default=None, help="an already built DB (must match --sample/--full)")
    a = ap.parse_args()
    sample = None if a.full else a.sample
    sample_ids = None
    if sample:
        from ripple.ingest.sample import sample_order_ids

        sample_ids = sample_order_ids(sample)
    if a.db:
        db = get_db(a.db, mode="embedded")
    else:
        from ripple.ingest.build import build_tenant

        db = get_db(Path(tempfile.mkdtemp()) / "scen.db", mode="embedded")
        build_tenant(TenantScope("dataco", db), sample)
    res = run(db, sample_ids)
    print(f"\nscenario eval: {res['exact']}/{res['total']} exact")
    close_db(db)
    return 0 if res["exact"] == res["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
