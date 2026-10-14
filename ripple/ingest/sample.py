"""Deterministic DataCo order sample for fast tests (pandas only, never touches the graph).

Half the sample comes from orders whose lane starts at a Shanghai, Ningbo or Shenzhen plant (so every scenario
has hits), the rest is a seeded random fill.
"""

from __future__ import annotations

import csv
import random

from ripple.ingest.dataco import order_frame, read_raw
from ripple.ingest.synth import SYNTH_DIR

PRIORITY_PORTS = ("PORT-CNSHA", "PORT-CNNGB", "PORT-CNSZX")


def _read(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def sample_order_ids(n: int, seed: int = 42) -> list[int]:
    d = SYNTH_DIR / "dataco"
    plants = {p["id"] for p in _read(d / "plants.csv") if p["port_id"] in PRIORITY_PORTS}
    prio_products = {int(x["product_id"].split("-")[1]) for x in _read(d / "product_plant.csv") if x["plant_id"] in plants}
    o = order_frame(read_raw())
    ids = o["Order Id"].tolist()
    prio = sorted(o.loc[o["first_product"].isin(prio_products), "Order Id"].tolist())
    rest = sorted(set(ids) - set(prio))
    rng = random.Random(seed)
    k = min(len(prio), n // 2)
    chosen = rng.sample(prio, k)
    chosen += rng.sample(rest, min(len(rest), n - k))
    return sorted(chosen)
