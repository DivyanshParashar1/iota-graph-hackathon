"""Expected scenario impact computed with pandas from data/raw + data/synthetic only (never the graph).

Definitions (same as the graph tools, see plan.md section 4):
* revenue of an order = round(sum(Sales of its items), 2); an order is at risk only if its status is open.
* port_closure: the order's lane (order_lane.csv) has origin or destination at an affected port.
* carrier_strike: the order's lane is operated by the striking carrier.
* supplier_failure: affected suppliers = the failed supplier plus everything downstream within 2 SUPPLIES_TO hops;
  a part is impacted when all of its suppliers are affected; an order is impacted when one of its products has an
  impacted part.

    python eval/ground_truth.py [--sample 3000]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ripple.ingest.dataco import OPEN_STATUSES, order_frame, read_raw  # noqa: E402
from ripple.scenarios import load_scenarios, scenario_event  # noqa: E402  (YAML only)

SYNTH = ROOT / "data" / "synthetic"


def _orders_and_lines(tenant: str, sample: list[int] | None):
    if tenant == "dataco":
        raw = read_raw()
        if sample is not None:
            raw = raw[raw["Order Id"].isin(set(sample))]
        o = order_frame(raw)
        orders = pd.DataFrame({"order_id": "ORD-" + o["Order Id"].astype(str), "total": o["total"],
                               "open": o["status"].isin(OPEN_STATUSES), "customer": "CUS-" + o["customer"].astype(str)})
        lines = pd.DataFrame({"order_id": "ORD-" + raw["Order Id"].astype(str),
                              "product_id": "PRD-" + raw["Product Card Id"].astype(str)})
    else:
        o = pd.read_csv(SYNTH / tenant / "orders.csv")
        orders = pd.DataFrame({"order_id": o["id"], "total": o["total"], "open": o["open"].astype(bool),
                               "customer": o["customer_id"]})
        ln = pd.read_csv(SYNTH / tenant / "order_lines.csv")
        lines = ln[["order_id", "product_id"]]
    return orders, lines


def resolve_targets(ev: dict, tenant: str) -> list[str]:
    d = SYNTH / tenant
    if ev.get("target_id"):
        return [ev["target_id"]]
    name = ev["target_name"].lower()
    if ev["type"] == "port_closure":
        ports = pd.read_csv(d / "ports.csv")
        return sorted(ports.loc[ports["name"].str.lower().str.contains(name, regex=False), "id"])
    if ev["type"] == "carrier_strike":
        lanes = pd.read_csv(d / "lanes.csv")
        return sorted(lanes.loc[lanes["carrier"].str.lower() == name, "id"])
    sups = pd.read_csv(d / "suppliers.csv")
    return sorted(sups.loc[sups["name"].str.lower().str.contains(name, regex=False), "id"])


def ground_truth(scenario_id: str, tenant: str = "dataco", sample: list[int] | None = None) -> dict:
    ev = scenario_event(scenario_id, tenant)
    d = SYNTH / tenant
    orders, lines = _orders_and_lines(tenant, sample)
    targets = resolve_targets(ev, tenant)
    ol = pd.read_csv(d / "order_lane.csv")
    lanes = pd.read_csv(d / "lanes.csv")
    if ev["type"] == "port_closure":
        hit_lanes = set(lanes.loc[lanes["origin"].isin(targets) | lanes["dest"].isin(targets), "id"])
        hit = set(ol.loc[ol["lane_id"].isin(hit_lanes), "order_id"])
    elif ev["type"] == "carrier_strike":
        hit = set(ol.loc[ol["lane_id"].isin(set(targets)), "order_id"])
    elif ev["type"] == "supplier_failure":
        st = pd.read_csv(d / "supplies_to.csv")
        down = st.groupby("src")["dst"].apply(set).to_dict()
        affected = set(targets)
        frontier = set(targets)
        for _ in range(2):
            frontier = set().union(*(down.get(x, set()) for x in frontier)) if frontier else set()
            affected |= frontier
        sup = pd.read_csv(d / "supplies.csv")
        by_part = sup.groupby("part_id")["supplier_id"].apply(set)
        parts = {p for p, s in by_part.items() if s <= affected}
        bom = pd.read_csv(d / "bom.csv")
        prods = set(bom.loc[bom["part_id"].isin(parts), "product_id"])
        hit = set(lines.loc[lines["product_id"].isin(prods), "order_id"])
    else:
        raise ValueError(ev["type"])
    at_risk = orders[orders["order_id"].isin(hit) & orders["open"]]
    return {"scenario": scenario_id, "tenant": tenant, "type": ev["type"], "targets": targets,
            "order_ids": sorted(at_risk["order_id"]), "orders": int(len(at_risk)),
            "revenue": round(float(at_risk["total"].sum()), 2), "customers": int(at_risk["customer"].nunique())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=None)
    ap.add_argument("--tenant", default="dataco")
    a = ap.parse_args()
    sample = None
    if a.sample:
        from ripple.ingest.sample import sample_order_ids

        sample = sample_order_ids(a.sample)
    print(f"{'scenario':28} {'orders':>7} {'revenue':>14} {'customers':>9}  targets")
    for sid in load_scenarios():
        gt = ground_truth(sid, a.tenant, sample)
        print(f"{sid:28} {gt['orders']:7d} {gt['revenue']:14,.2f} {gt['customers']:9d}  {gt['targets'][:3]}"
              f"{'...' if len(gt['targets']) > 3 else ''}")


if __name__ == "__main__":
    main()
