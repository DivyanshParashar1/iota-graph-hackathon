"""Load test: N concurrent sessions across both tenants (in-process threads sharing one DB, like the API).

Each session runs reads (blast-radius numbers, brain question, doc search, chokepoints) and writes (duplicate
action proposals, tool-call logging). Afterwards it checks: zero cross-tenant ids in any result and zero
duplicate Action nodes. Prints p50/p95 latency per operation.

    python eval/load_test.py [--db PATH] [--sessions 20]
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ripple.db import TenantScope, close_db, get_db  # noqa: E402
from ripple.scenarios import scenario_event  # noqa: E402
from ripple.tools.actions import propose_action  # noqa: E402
from ripple.tools.algos import single_points_of_failure  # noqa: E402
from ripple.tools.base import call_context  # noqa: E402
from ripple.tools.brain import ask, doc_search  # noqa: E402
from ripple.tools.impact import blast_radius, revenue_at_risk, trigger  # noqa: E402

TYPED = re.compile(r"^(SUP|PRT|PORT|ORD|CUS|LANE|PRD|EMP|DOC|THR|MSG|PLT|TEAM|CON|DEC|OL|MKT|REG|PB|EPI)-")


def foreign(tenant: str, ids) -> list[str]:
    """Typed ids that belong to the other tenant (nova ids carry -N- after the type prefix)."""
    out = []
    for i in ids:
        if not isinstance(i, str) or not TYPED.match(i):
            continue
        is_nova = "-N-" in i or i.startswith(("PB-N-", "EPI-N-"))
        if (tenant == "nova") != is_nova:
            out.append(i)
    return out


def setup(db) -> dict[str, str]:
    """One open incident per tenant; caches warmed like the API does at startup."""
    from ripple.tools.algos import warm_caches

    incidents = {}
    for t in ("dataco", "nova"):
        s = TenantScope(t, db)
        warm_caches(s)
        with call_context(no_log=True):
            did, iid = trigger(s, scenario_event("port_closure_shanghai", t))
            blast_radius(s, disruption_id=did)
        incidents[t] = iid
    return incidents


def session(db, tenant: str, iid: str, k: int, lat: dict, leaks: list, errors: list, lock) -> None:
    s = TenantScope(tenant, db)

    def timed(name, fn):
        t0 = time.perf_counter()
        r = fn()
        with lock:
            lat.setdefault(name, []).append((time.perf_counter() - t0) * 1000)
            bad = foreign(tenant, list(r.node_ids) + [e for edge in r.edges for e in (edge[0], edge[2])])
            if bad:
                leaks.append((tenant, name, bad[:5]))
        return r

    try:
        with call_context(agent=f"load-{tenant}-{k}", incident_id=iid):
            timed("revenue_at_risk", lambda: revenue_at_risk(s, incident_id=iid))
            timed("ask", lambda: ask(s, question="Who on the team has handled a port closure before?"))
            timed("doc_search", lambda: doc_search(s, query="delay penalty force majeure", k=5))
            timed("single_points_of_failure", lambda: single_points_of_failure(s, top_k=5))
            port = "PORT-CNSHA" if tenant == "dataco" else "PORT-N-CNSHA"
            for _ in range(3):  # the same proposal from every session: must stay one Action
                timed("propose_action", lambda: propose_action(
                    s, incident_id=iid, type="NOTIFY_OWNER", params={"text": "load test", "employee_id": None},
                    evidence_ids=[port], agent="planner", summary="load test"))
    except Exception as e:  # noqa: BLE001
        with lock:
            errors.append((tenant, k, repr(e)))


def run_load_test(db, sessions: int = 20) -> dict:
    incidents = setup(db)
    lat: dict[str, list[float]] = {}
    leaks: list = []
    errors: list = []
    lock = threading.Lock()
    threads = [threading.Thread(target=session, args=(db, ("dataco", "nova")[k % 2], incidents[("dataco", "nova")[k % 2]],
                                                       k, lat, leaks, errors, lock)) for k in range(sessions)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.time() - t0
    dup = {}
    for t, iid in incidents.items():
        rows = TenantScope(t, db).ops.query("MATCH (a:Action)-[:FOR_INCIDENT]->(:Incident {id: $iid}) "
                                             "RETURN a.id AS id, count(*) AS c", {"iid": iid})
        nodes = TenantScope(t, db).ops.query("MATCH (a:Action {summary: 'load test'}) RETURN count(a) AS c")[0]["c"]
        dup[t] = {"actions": len(rows), "load_test_action_nodes": nodes}
    duplicates = sum(max(0, v["load_test_action_nodes"] - 1) for v in dup.values())
    stats = {k: {"n": len(v), "p50_ms": round(statistics.median(v), 1),
                 "p95_ms": round(sorted(v)[max(0, int(len(v) * 0.95) - 1)], 1)} for k, v in sorted(lat.items())}
    return {"sessions": sessions, "wall_s": round(wall, 2), "ops": sum(len(v) for v in lat.values()),
            "leaks": leaks, "duplicates": duplicates, "errors": errors, "latency": stats, "actions": dup}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--sessions", type=int, default=20)
    a = ap.parse_args()
    if a.db:
        db = get_db(a.db, mode="embedded")
    else:
        from ripple.ingest.build import build_all

        db = get_db(Path(tempfile.mkdtemp()) / "load.db", mode="embedded")
        build_all(db, 3000)
    r = run_load_test(db, a.sessions)
    print(f"{r['sessions']} sessions, {r['ops']} ops in {r['wall_s']}s; cross-tenant leaks: {len(r['leaks'])}; "
          f"duplicate actions: {r['duplicates']}; errors: {len(r['errors'])}")
    for k, v in r["latency"].items():
        print(f"  {k:26} n={v['n']:3d}  p50 {v['p50_ms']:8.1f} ms  p95 {v['p95_ms']:8.1f} ms")
    close_db(db)
    return 0 if not r["leaks"] and not r["duplicates"] and not r["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
