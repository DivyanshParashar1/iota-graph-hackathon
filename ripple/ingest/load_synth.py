"""Synthetic files (data/synthetic/<tenant>/*.csv) -> graph."""

from __future__ import annotations

import csv
import time
from pathlib import Path

from ripple.db import TenantScope
from ripple.ingest.synth import SYNTH_DIR

INTS = {"tier", "capacity", "qty", "lead_time_days", "sla_days", "penalty_cap_pct", "late_risk", "days_real",
        "days_sched", "version"}
FLOATS = {"lat", "lon", "risk_score", "reliability", "transit_days", "unit_cost", "share", "price", "total",
          "profit", "penalty_pct", "port_km"}
BOOLS = {"force_majeure", "exclusivity", "open"}


def read_csv(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with open(path) as f:
        for r in csv.DictReader(f):
            for k, v in r.items():
                if k in INTS:
                    r[k] = int(v)
                elif k in FLOATS:
                    r[k] = float(v)
                elif k in BOOLS:
                    r[k] = v == "True"
                elif k == "valid_to":
                    r[k] = v or None
            rows.append(r)
    return rows


def _batched(g, qname: str, rows: list[dict], n: int = 5000) -> None:
    for i in range(0, len(rows), n):
        g.run(qname, {"rows": rows[i : i + n]})


def load_nova_orders(scope: TenantScope) -> dict:
    """Nova Retail has its own synthetic products/customers/orders (no DataCo rows)."""
    from ripple.ingest.dataco import slug

    d = SYNTH_DIR / scope.tenant_id
    g = scope.ops
    g.run("load_products", {"rows": read_csv(d / "products.csv")})
    orders = read_csv(d / "orders.csv")
    regions = sorted({(o["market"], o["region"]) for o in orders})
    g.run("load_regions", {"rows": [{"market_id": f"MKT-N-{slug(m)}", "market": m, "region_id": f"REG-N-{slug(r)}",
                                     "region": r} for m, r in regions]})
    _batched(g, "load_customers", read_csv(d / "customers.csv"))
    for o in orders:
        o["market_id"] = f"MKT-N-{slug(o['market'])}"
        o["region_id"] = f"REG-N-{slug(o['region'])}"
    _batched(g, "load_orders", orders)
    lines = read_csv(d / "order_lines.csv")
    _batched(g, "load_order_lines", lines)
    return {"orders": len(orders), "lines": len(lines)}


def load_synth(scope: TenantScope) -> dict:
    t0 = time.time()
    d = SYNTH_DIR / scope.tenant_id
    g = scope.ops
    counts = {}
    steps = [("ports", "load_ports"), ("plants", "load_plants"), ("product_plant", "load_product_plant"),
             ("lanes", "load_lanes"), ("connects", "load_connects"), ("order_lane", "load_order_lane"),
             ("suppliers", "load_suppliers"), ("supplies_to", "load_supplies_to"), ("parts", "load_parts"),
             ("bom", "load_bom"), ("supplies", "load_supplies"), ("qualified", "load_qualified"),
             ("teams", "load_teams"), ("employees", "load_employees"), ("ownership", "load_ownership"),
             ("contracts", "load_contracts")]
    for fname, qname in steps:
        rows = read_csv(d / f"{fname}.csv")
        _batched(g, qname, rows)
        counts[fname] = len(rows)
    counts["seconds"] = round(time.time() - t0, 2)
    return counts
