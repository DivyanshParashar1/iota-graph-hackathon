"""Build a tenant end to end: schema, orders, synthetic layer, documents, memory seed.

    python -m ripple.ingest.build --tenant dataco|nova|all [--sample 3000] [--db var/ripple.db] [--fresh]
"""

from __future__ import annotations

import argparse
import time

from ripple.db import DB, TenantScope, get_db


def build_tenant(scope: TenantScope, sample: int | None = None, fresh: bool = True) -> dict:
    from ripple.graph.schema import apply_schema
    from ripple.ingest.docs import ingest_docs
    from ripple.ingest.load_synth import load_nova_orders, load_synth
    from ripple.tools.memory import seed_memory

    t0 = time.time()
    if fresh:
        scope.ops.delete()
        scope.mem.delete()
    apply_schema(scope)
    out: dict = {"tenant": scope.tenant_id}
    if scope.tenant_id == "dataco":
        from ripple.ingest.dataco import load_dataco

        ids = None
        if sample:
            from ripple.ingest.sample import sample_order_ids

            ids = sample_order_ids(sample)
        out["dataco"] = load_dataco(scope, ids)
    else:
        out["orders"] = load_nova_orders(scope)
    out["synth"] = load_synth(scope)
    out["docs"] = ingest_docs(scope)
    out["memory"] = seed_memory(scope)
    scope.save()
    out["seconds"] = round(time.time() - t0, 2)
    return out


def build_all(db: DB, sample: int | None = None, tenants=("dataco", "nova")) -> list[dict]:
    return [build_tenant(TenantScope(t, db), sample) for t in tenants]


def is_built(db: DB, tenant: str) -> bool:
    try:
        r = TenantScope(tenant, db).ops.query("MATCH (n:Order) RETURN count(n) AS c")
        return bool(r and r[0]["c"])
    except Exception:  # noqa: BLE001
        return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", default="all")
    ap.add_argument("--sample", type=int, default=None)
    ap.add_argument("--db", default=None)
    a = ap.parse_args()
    db = get_db(a.db) if a.db else get_db()
    tenants = ("dataco", "nova") if a.tenant == "all" else (a.tenant,)
    for r in build_all(db, a.sample, tenants):
        print(r)
    db.close()


if __name__ == "__main__":
    main()
