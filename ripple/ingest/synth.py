"""Deterministic synthetic layer generator -> data/synthetic/<tenant>/.

DataCo has no suppliers, BOM, ports, lanes or org chart, so we generate them from a fixed seed (42 for
dataco, 7 for nova). Loaders and eval/ground_truth.py read only the files written here. Every synthetic
company and person is tagged [SYNTH]; emails use @ripple-demo.example.

    python -m ripple.ingest.synth --tenant dataco|nova|all
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path

from faker import Faker

from ripple import ROOT
from ripple.geo import PORTS, haversine_km

SYNTH_DIR = ROOT / "data" / "synthetic"

MODES = {"Standard Class": ("STD", 1.0), "Second Class": ("SEC", 0.8), "First Class": ("FST", 0.6),
         "Same Day": ("SDY", 0.4)}
SEA_CARRIERS = ["Blue Meridian Lines", "Pacific Arc Shipping", "Northstar Freight", "Cobalt Ocean Carriers"]
AIR_CARRIERS = ["Atlas Air Cargo", "Skybridge Express"]
CARRIERS = SEA_CARRIERS + AIR_CARRIERS
KM_PER_DAY = 600.0

# Order Region -> destination port
REGION_PORT = {
    "Western Europe": "NLRTM", "Northern Europe": "DEHAM", "Southern Europe": "ESVLC", "Eastern Europe": "DEHAM",
    "Central America": "MXZLO", "Caribbean": "PAONX", "South America": "BRSSZ", "West of USA": "USLAX",
    "US Center": "USLGB", "East of USA": "USNYC", "South of  USA": "USSAV", "Canada": "USNYC", "Oceania": "AUSYD",
    "Southeast Asia": "SGSIN", "South Asia": "INNSA", "Eastern Asia": "HKHKG", "West Asia": "AEJEA",
    "Central Asia": "AEJEA", "North Africa": "ESVLC", "West Africa": "ZADUR", "East Africa": "ZADUR",
    "Central Africa": "ZADUR", "Southern Africa": "ZADUR",
}

# (code, name, country, lat, lon, port, weight)
PLANTS = [
    ("01", "Shanghai Pudong Plant", "CN", 31.22, 121.54, "CNSHA", 0.18),
    ("02", "Ningbo Beilun Plant", "CN", 29.89, 121.84, "CNNGB", 0.12),
    ("03", "Shenzhen Bao'an Plant", "CN", 22.55, 113.88, "CNSZX", 0.16),
    ("04", "Qingdao Huangdao Plant", "CN", 35.96, 120.18, "CNTAO", 0.08),
    ("05", "Binh Duong Plant", "VN", 11.17, 106.65, "VNSGN", 0.10),
    ("06", "Pune Chakan Plant", "IN", 18.76, 73.86, "INNSA", 0.10),
    ("07", "Shah Alam Plant", "MY", 3.07, 101.52, "MYPKG", 0.04),
    ("08", "Taichung Plant", "TW", 24.15, 120.67, "TWKHH", 0.04),
    ("09", "Changwon Plant", "KR", 35.23, 128.68, "KRPUS", 0.04),
    ("10", "Guadalajara Plant", "MX", 20.67, -103.35, "MXZLO", 0.05),
    ("11", "Izmir Plant", "TR", 38.42, 27.14, None, 0.04),  # port = nearest
    ("12", "Atlanta Plant", "US", 33.75, -84.39, "USSAV", 0.05),
]

COUNTRY_WEIGHTS = [("CN", 35), ("VN", 10), ("IN", 10), ("TW", 7), ("KR", 6), ("MY", 5), ("MX", 6), ("US", 8),
                   ("DE", 5), ("TR", 4), ("BR", 4)]
COUNTRY_CENTER = {"TR": (39.9, 32.9)}

EXTRA_LANES = [  # port-to-port transshipment lanes (Standard Class) that give alt_route real choices
    ("CNSHA", "SGSIN"), ("CNNGB", "SGSIN"), ("CNSZX", "HKHKG"), ("HKHKG", "SGSIN"), ("CNTAO", "KRPUS"),
    ("KRPUS", "USLAX"), ("HKHKG", "USLAX"), ("TWKHH", "USLGB"), ("SGSIN", "NLRTM"), ("SGSIN", "AEJEA"),
    ("AEJEA", "NLRTM"), ("SGSIN", "AUSYD"), ("SGSIN", "INNSA"), ("SGSIN", "ZADUR"), ("ZADUR", "BRSSZ"),
    ("PAONX", "USNYC"), ("PAONX", "USSAV"), ("MXZLO", "USLAX"), ("NLRTM", "USNYC"), ("BEANR", "USNYC"),
    ("GBFXT", "USNYC"), ("NLRTM", "BEANR"), ("NLRTM", "GBFXT"), ("DEHAM", "NLRTM"), ("ESVLC", "NLRTM"),
    ("ESVLC", "USNYC"), ("USLAX", "PAONX"), ("CNNGB", "USLAX"), ("CNSHA", "KRPUS"), ("CNNGB", "HKHKG"),
    ("VNSGN", "SGSIN"), ("MYPKG", "SGSIN"), ("CNTAO", "CNSHA"), ("CNNGB", "CNSHA"), ("CNSZX", "CNNGB"),
    ("TWKHH", "HKHKG"), ("INNSA", "AEJEA"), ("BRSSZ", "PAONX"),
]

# Part families per department group: (base names, unit cost range)
PART_FAMILIES = {
    "Apparel": (["Fabric panel", "Zipper", "Thread spool", "Woven label", "Dye lot", "Button set", "Elastic band"], (0.2, 6)),
    "Footwear": (["Rubber sole", "Mesh upper", "Laces", "Eyelets", "Insole foam", "Heel counter"], (0.3, 12)),
    "Golf": (["Graphite shaft", "Rubber grip", "Titanium club head", "Ferrule", "Ball core"], (1, 40)),
    "Electronics": (["PCB assembly", "Polymer casing", "LCD display", "Motion sensor", "Charging cable",
                     "Steel frame", "Resistance cord", "Bluetooth module"], (1, 35)),
    "Fan Shop": (["Printed fabric", "Foam core", "Molded shell", "Team decal", "Aluminum tube", "Canvas sheet"], (0.5, 20)),
    "Outdoors": (["Aluminum frame", "Nylon fabric", "Side-release buckle", "Waterproof coating", "Foam padding",
                  "Carabiner", "Tent pole", "Mesh panel"], (0.3, 25)),
    "Discs Shop": (["Polymer disc blank", "Foil stamp", "Pigment batch"], (0.2, 4)),
    "Book Shop": (["Paper stock", "Ink cartridge", "Binding glue"], (0.1, 3)),
    "Pet Shop": (["Nylon webbing", "Plastic buckle", "Foam bed insert"], (0.2, 8)),
    "Health and Beauty": (["Bottle", "Pump dispenser", "Fragrance base"], (0.1, 5)),
}
DEPT_GROUP = {"Technology": "Electronics", "Fitness": "Electronics"}
CHOKE_GROUPS = [("Outdoors", "Discs Shop", "Book Shop", "Pet Shop", "Health and Beauty"), ("Footwear", "Golf"),
                ("Electronics", "Apparel")]
HERO_PART = "Li-ion battery pack"
HERO_SUPPLIER = "Shenzhen Volt Components [SYNTH]"

TEAMS = [("PROC", "Procurement", 10, ["Category Manager", "Sourcing Specialist", "Supplier Relationship Manager"]),
         ("LOG", "Logistics", 8, ["Logistics Lead", "Transport Planner", "Customs Specialist"]),
         ("PLAN", "Planning", 6, ["Demand Planner", "Supply Planner"]),
         ("QA", "Quality", 6, ["Quality Engineer", "Supplier Quality Lead"]),
         ("LEGAL", "Legal", 4, ["Commercial Counsel", "Contracts Manager"]),
         ("COPS", "Customer Ops", 6, ["Customer Ops Manager", "Account Specialist"])]
# Fixed hero employees (dataco). (team, name, role)
HEROES = [("PROC", "Priya Raman [SYNTH]", "Category Manager"),
          ("PROC", "Daniel Okafor [SYNTH]", "Supplier Relationship Manager"),
          ("LOG", "Lena Fischer [SYNTH]", "Logistics Lead"),
          ("LEGAL", "Marcus Bell [SYNTH]", "Commercial Counsel"),
          ("PROC", "Hiro Tanaka [SYNTH]", "Sourcing Specialist")]


@dataclass
class TenantCfg:
    tenant: str
    seed: int
    p: str  # id prefix after the type, "" for dataco, "N-" for nova
    n_t1: int
    n_t2: int
    n_t3: int
    choke_in: tuple[int, int]
    choke_out: tuple[int, int]
    n_contracts: int
    n_employees: int
    n_chats: int


CFGS = {
    "dataco": TenantCfg("dataco", 42, "", 150, 300, 200, (15, 18), (20, 24), 60, 40, 30),
    "nova": TenantCfg("nova", 7, "N-", 15, 30, 20, (3, 4), (3, 4), 8, 12, 6),
}


def _r(x: float, n: int = 2) -> float:
    return round(float(x), n)


class Gen:
    def __init__(self, cfg: TenantCfg):
        self.c = cfg
        self.rng = random.Random(cfg.seed)
        self.fake = Faker("en_US")
        self.fake.seed_instance(cfg.seed)
        self.files: dict[str, list[dict]] = {}
        self.json: dict[str, object] = {}

    def pid(self, typ: str, rest: str) -> str:
        return f"{typ}-{self.c.p}{rest}"

    # ---------------------------------------------------------------- products and orders
    def products(self) -> list[dict]:
        if self.c.tenant == "dataco":
            from ripple.ingest.dataco import read_raw

            df = read_raw().drop_duplicates("Product Card Id").sort_values("Product Card Id")
            return [{"id": f"PRD-{r['Product Card Id']}", "name": r["Product Name"], "category": r["Category Name"],
                     "department": r["Department Name"], "price": float(r["Product Price"])} for _, r in df.iterrows()]
        catalog = [("Trail Runner Shoe", "Running", "Footwear", 89.0), ("Waterproof Hiking Boot", "Hiking", "Footwear", 139.0),
                   ("Kids Sneaker", "Kids", "Footwear", 45.0), ("Merino Base Layer", "Layers", "Apparel", 69.0),
                   ("Rain Shell Jacket", "Outerwear", "Apparel", 159.0), ("Everyday Hoodie", "Casual", "Apparel", 55.0),
                   ("Smart Fitness Band", "Wearables", "Technology", 79.0), ("GPS Sport Watch", "Wearables", "Technology", 249.0),
                   ("Wireless Earbuds", "Audio", "Technology", 99.0), ("Ultralight Tent", "Camping", "Outdoors", 299.0),
                   ("Trekking Pole Pair", "Hiking", "Outdoors", 59.0), ("Insulated Bottle", "Camping", "Outdoors", 29.0)]
        return [{"id": self.pid("PRD", f"{i + 1:02d}"), "name": f"Nova {n}", "category": cat, "department": d,
                 "price": pr} for i, (n, cat, d, pr) in enumerate(catalog)]

    def nova_orders(self, products: list[dict]) -> None:
        """Nova Retail's own synthetic customers, orders and lines (no DataCo rows)."""
        rng = self.rng
        regions = [("Western Europe", "Europe"), ("Northern Europe", "Europe"), ("West of USA", "USCA"),
                   ("East of USA", "USCA"), ("Southeast Asia", "Pacific Asia"), ("Oceania", "Pacific Asia"),
                   ("South America", "LATAM")]
        segs = ["Consumer", "Corporate", "Home Office"]
        customers = []
        for i in range(600):
            reg, mkt = rng.choice(regions)
            customers.append({"id": self.pid("CUS", f"{i + 1:04d}"), "segment": rng.choice(segs),
                              "city": self.fake.city(), "state": self.fake.state_abbr(), "country": mkt,
                              "region": reg, "market": mkt})
        statuses = ["COMPLETE"] * 4 + ["CLOSED"] + ["PENDING", "PROCESSING", "PENDING_PAYMENT", "ON_HOLD", "PAYMENT_REVIEW"]
        late = {"Standard Class": 0.38, "Second Class": 0.77, "First Class": 0.95, "Same Day": 0.46}
        orders, lines = [], []
        ln = 1
        for i in range(3000):
            cu = rng.choice(customers)
            mode = rng.choices(list(MODES), weights=[60, 20, 15, 5])[0]
            st = rng.choice(statuses)
            items = []
            for _ in range(rng.randint(1, 4)):
                pr = rng.choice(products)
                q = rng.randint(1, 4)
                items.append({"id": self.pid("OL", f"{ln:06d}"), "order_id": self.pid("ORD", f"{i + 1:05d}"),
                              "product_id": pr["id"], "qty": q, "total": _r(q * pr["price"]), "price": pr["price"]})
                ln += 1
            sched = {"Standard Class": 4, "Second Class": 2, "First Class": 1, "Same Day": 0}[mode]
            lr = 1 if rng.random() < late[mode] else 0
            orders.append({
                "id": self.pid("ORD", f"{i + 1:05d}"), "date": f"2026-{rng.randint(1, 9):02d}-{rng.randint(1, 28):02d}T"
                f"{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}", "status": st,
                "open": st not in ("COMPLETE", "CLOSED"), "region": cu["region"], "market": cu["market"],
                "country": cu["country"], "city": cu["city"], "total": _r(sum(x["total"] for x in items)),
                "profit": _r(sum(x["total"] for x in items) * rng.uniform(-0.1, 0.3)), "late_risk": lr,
                "delivery_status": "Late delivery" if lr else "Shipping on time", "days_real": sched + lr * rng.randint(1, 3),
                "days_sched": sched, "shipping_mode": mode, "customer_id": cu["id"], "first_product": items[0]["product_id"]})
            lines += items
        self.files["customers"] = customers
        self.files["orders"] = orders
        self.files["order_lines"] = lines

    # ---------------------------------------------------------------- geography
    def geography(self, products: list[dict]) -> None:
        rng = self.rng
        P = self.c.p
        ports = [{"id": f"PORT-{P}{code}", "code": code, "name": n, "country": c, "lat": la, "lon": lo,
                  "status": "open", "risk_score": _r(rng.uniform(0.1, 0.4))} for code, (n, c, la, lo) in PORTS.items()]
        self.files["ports"] = ports
        self.port_code = {p["id"]: p["code"] for p in ports}
        plants = []
        for code, name, ctry, la, lo, port, w in PLANTS:
            if port is None:
                port = min(PORTS, key=lambda k: haversine_km(la, lo, PORTS[k][2], PORTS[k][3]))
            km = haversine_km(la, lo, PORTS[port][2], PORTS[port][3])
            plants.append({"id": self.pid("PLT", code), "name": name + " [SYNTH]", "country": ctry, "lat": la, "lon": lo,
                           "port_id": f"PORT-{P}{port}", "port_km": _r(km, 1), "weight": w})
        self.files["plants"] = plants
        weights = [p["weight"] for p in plants]
        pp = []
        for pr in products:  # products are sorted by id
            pl = rng.choices(plants, weights=weights)[0]
            pp.append({"product_id": pr["id"], "plant_id": pl["id"]})
        self.files["product_plant"] = pp

    def transit(self, o: str, d: str, mult: float) -> float:
        a, b = PORTS[o], PORTS[d]
        return max(1.0, _r(haversine_km(a[2], a[3], b[2], b[3]) / KM_PER_DAY * mult, 1))

    def lanes(self, orders: list[dict]) -> None:
        """One lane per (plant port, destination port, mode) actually used, plus transshipment lanes."""
        rng = self.rng
        P = self.c.p
        plant_port = {p["id"]: p["port_id"] for p in self.files["plants"]}
        prod_plant = {x["product_id"]: x["plant_id"] for x in self.files["product_plant"]}
        order_lane, used = [], {}
        for o in orders:  # sorted by id
            orig = self.port_code[plant_port[prod_plant[o["first_product"]]]]
            dest = REGION_PORT[o["region"]]
            code, _ = MODES[o["shipping_mode"]]
            lid = f"LANE-{P}{orig}-{dest}-{code}"
            used[lid] = (orig, dest, o["shipping_mode"])
            order_lane.append({"order_id": o["id"], "lane_id": lid})
        for o, d in EXTRA_LANES:
            used.setdefault(f"LANE-{P}{o}-{d}-STD", (o, d, "Standard Class"))
        lanes = []
        for lid in sorted(used):
            o, d, mode = used[lid]
            code, mult = MODES[mode]
            carrier = rng.choice(AIR_CARRIERS if code == "SDY" else SEA_CARRIERS)
            lanes.append({"id": lid, "origin": f"PORT-{P}{o}", "dest": f"PORT-{P}{d}", "mode": mode,
                          "transit_days": self.transit(o, d, mult), "carrier": carrier,
                          "risk_score": _r(rng.uniform(0.05, 0.35))})
        self.files["lanes"] = lanes
        self.files["order_lane"] = order_lane
        # CONNECTS: sea days (Standard multiplier) for every port pair joined by a lane, both directions
        conn = {}
        for ln in lanes:
            o, d = self.port_code[ln["origin"]], self.port_code[ln["dest"]]
            if o == d:
                continue
            t = self.transit(o, d, 1.0)
            for a, b in ((o, d), (d, o)):
                conn[(a, b)] = min(conn.get((a, b), 1e9), t)
        self.files["connects"] = [{"src": f"PORT-{P}{a}", "dst": f"PORT-{P}{b}", "transit_days": t}
                                  for (a, b), t in sorted(conn.items())]

    # ---------------------------------------------------------------- suppliers and BOM
    def _company(self, used: set[str]) -> str:
        while True:
            n = self.fake.company().replace(",", "") + " [SYNTH]"
            if n not in used and n != HERO_SUPPLIER:
                used.add(n)
                return n

    def _locate(self, country: str) -> tuple[float, float, str]:
        rng = self.rng
        ports = [k for k, v in PORTS.items() if v[1] == country]
        if ports:
            k = rng.choice(sorted(ports))
            lat, lon = PORTS[k][2] + rng.uniform(-1.0, 1.0), PORTS[k][3] + rng.uniform(-1.0, 1.0)
        else:
            la, lo = COUNTRY_CENTER[country]
            lat, lon = la + rng.uniform(-1.5, 1.5), lo + rng.uniform(-2.5, 2.5)
        cands = ports or list(PORTS)
        port = min(sorted(cands), key=lambda k: haversine_km(lat, lon, PORTS[k][2], PORTS[k][3]))
        return _r(lat, 3), _r(lon, 3), f"PORT-{self.c.p}{port}"

    def suppliers(self) -> None:
        rng, c = self.rng, self.c
        used: set[str] = set()
        ctry = [x for x, _ in COUNTRY_WEIGHTS]
        w = [x for _, x in COUNTRY_WEIGHTS]
        sups = []
        for tier, n in ((1, c.n_t1), (2, c.n_t2), (3, c.n_t3)):
            for i in range(n):
                sid = self.pid("SUP", f"T{tier}-{i + 1:04d}")
                if c.tenant == "dataco" and tier == 1 and i == 0:
                    name, country = HERO_SUPPLIER, "CN"
                    lat, lon, port = 22.65, 114.05, f"PORT-{c.p}CNSZX"
                else:
                    name, country = self._company(used), rng.choices(ctry, weights=w)[0]
                    lat, lon, port = self._locate(country)
                sups.append({"id": sid, "name": name, "tier": tier, "country": country, "lat": lat, "lon": lon,
                             "port_id": port, "capacity": rng.randint(5, 200) * 100,
                             "reliability": _r(rng.uniform(0.6, 0.99)), "risk_score": _r(rng.uniform(0.05, 0.6))})
        self.files["suppliers"] = sups
        t1 = [s for s in sups if s["tier"] == 1]
        t2 = [s for s in sups if s["tier"] == 2]
        t3 = [s for s in sups if s["tier"] == 3]
        # planted chokepoints: tier-2 hubs with exclusive tier-3 inputs and many tier-1 outputs
        chokes = [t2[i] for i in sorted(rng.sample(range(len(t2)), 3))]
        free_t3 = [s["id"] for s in t3]
        rng.shuffle(free_t3)
        # tier-1 specialties: each tier-1 supplier makes parts for one primary department group (+30% a second)
        groups = sorted(PART_FAMILIES)
        self.specialty = {}
        for i, s in enumerate(t1):
            sp = [groups[i % len(groups)]]
            if rng.random() < 0.3:
                sp.append(rng.choice([g for g in groups if g != sp[0]]))
            if i == 0 and c.tenant == "dataco":
                sp = ["Electronics"]
            self.specialty[s["id"]] = sp
        edges, choke_info = [], []
        taken: set[str] = {t1[0]["id"]}  # the hero supplier is never downstream of a chokepoint
        for k, ch in enumerate(chokes):
            ins = [free_t3.pop() for _ in range(rng.randint(*c.choke_in))]
            # each chokepoint feeds tier-1s of a few department groups (CHOKE_GROUPS[k]) so its blast radius is
            # concentrated, like a resin or textile supplier in real life
            pref = [s["id"] for s in t1 if s["id"] not in taken and self.specialty[s["id"]][0] in CHOKE_GROUPS[k]]
            rest = [s["id"] for s in t1 if s["id"] not in taken and s["id"] not in pref]
            rng.shuffle(pref)
            rng.shuffle(rest)
            pool = pref + rest
            outs = pool[: rng.randint(*c.choke_out)]
            taken |= set(outs)
            edges += [(x, ch["id"]) for x in ins] + [(ch["id"], y) for y in outs]
            choke_info.append({"id": ch["id"], "name": ch["name"], "inputs": sorted(ins), "outputs": sorted(outs)})
        normal_t2 = [s["id"] for s in t2 if s["id"] not in {x["id"] for x in chokes}]
        for x in sorted(free_t3):
            for y in rng.sample(normal_t2, rng.randint(1, 2)):
                edges.append((x, y))
        t1_ids = [s["id"] for s in t1]
        for x in normal_t2:
            for y in rng.sample(t1_ids, rng.randint(1, 2)):
                edges.append((x, y))
        self.files["supplies_to"] = [{"src": a, "dst": b} for a, b in sorted(set(edges))]
        self.chokes = choke_info
        self.choke_downstream = {y for ch in choke_info for y in ch["outputs"]}

    def parts_and_bom(self, products: list[dict]) -> None:
        rng = self.rng
        groups: dict[str, list[dict]] = {}
        for pr in products:
            groups.setdefault(DEPT_GROUP.get(pr["department"], pr["department"]), []).append(pr)
        parts, bom = [], []
        n = 0
        for gname in sorted(groups):
            prods = groups[gname]
            bases, (lo, hi) = PART_FAMILIES.get(gname, PART_FAMILIES["Outdoors"])
            size = max(6, 5 * len(prods) + 3)
            pool = []
            if gname == "Electronics" and self.c.tenant == "dataco":
                pool.append((HERO_PART, "Battery", "high"))
            k = 0
            while len(pool) < size:
                b = bases[k % len(bases)]
                pool.append((f"{b} type {k // len(bases) + 1}", b, rng.choice(["low", "medium", "medium", "high"])))
                k += 1
            gparts = []
            for name, fam, crit in pool:
                n += 1
                gparts.append({"id": self.pid("PRT", f"{n:04d}"), "name": name if not self.c.p else f"{name} (Nova)",
                               "category": fam, "department": gname, "unit_cost": _r(rng.uniform(lo, hi)),
                               "criticality": crit})
            usage: dict[str, int] = {}
            for pr in prods:
                kk = min(len(gparts), rng.randint(3, 8))
                chosen = rng.sample(gparts, kk)
                if gname == "Electronics" and self.c.tenant == "dataco" and pr["department"] == "Technology":
                    if gparts[0] not in chosen:
                        chosen[-1] = gparts[0]
                for pt in chosen:
                    bom.append({"part_id": pt["id"], "product_id": pr["id"], "qty": rng.randint(1, 4)})
                    usage[pt["id"]] = usage.get(pt["id"], 0) + 1
            # parts no product picked go to the product with the fewest parts, so every part is used
            count = {pr["id"]: sum(1 for b in bom if b["product_id"] == pr["id"]) for pr in prods}
            for pt in gparts:
                if pt["id"] not in usage:
                    tgt = min(prods, key=lambda x: (count[x["id"]], x["id"]))
                    bom.append({"part_id": pt["id"], "product_id": tgt["id"], "qty": rng.randint(1, 4)})
                    count[tgt["id"]] += 1
                    usage[pt["id"]] = 1
            parts += gparts
        self.files["parts"] = parts
        self.files["bom"] = sorted(bom, key=lambda x: (x["part_id"], x["product_id"]))

    def supplies(self) -> None:
        rng = self.rng
        parts = self.files["parts"]
        t1 = [s for s in self.files["suppliers"] if s["tier"] == 1]
        t1_ids = [s["id"] for s in t1]
        hero_sid = t1_ids[0]
        n_single = round(0.2 * len(parts))
        hero_pid = next((p["id"] for p in parts if p["name"] == HERO_PART), None)
        others = [p["id"] for p in parts if p["id"] != hero_pid]
        single = set(rng.sample(others, n_single - (1 if hero_pid else 0)))
        if hero_pid:
            single.add(hero_pid)
        supplies = []
        spec_of = {g: [sid for sid in t1_ids if g in self.specialty[sid]] for g in PART_FAMILIES}
        for p in parts:
            cands = spec_of.get(p["department"]) or t1_ids
            cands1 = [x for x in cands if x != hero_sid] or t1_ids[1:]
            if p["id"] == hero_pid:
                sids = [hero_sid]
            elif p["id"] in single:
                sids = [rng.choice(cands1)]
            else:
                sids = rng.sample(cands, min(len(cands), rng.randint(2, 6)))
            ws = [rng.uniform(0.5, 1.5) for _ in sids]
            shares = [_r(x / sum(ws), 4) for x in ws]
            shares[-1] = _r(1.0 - sum(shares[:-1]), 4)
            for sid, sh in zip(sids, shares):
                supplies.append({"supplier_id": sid, "part_id": p["id"], "lead_time_days": rng.randint(7, 45),
                                 "unit_cost": _r(p["unit_cost"] * rng.uniform(0.9, 1.15)), "share": sh})
        # the hero supplier also supplies a few other electronics parts (shared with others)
        self.files["supplies"] = sorted(supplies, key=lambda x: (x["part_id"], x["supplier_id"]))
        # qualified alternates: outside CN, not downstream of a chokepoint, not already supplying
        by_part: dict[str, set[str]] = {}
        for s in supplies:
            by_part.setdefault(s["part_id"], set()).add(s["supplier_id"])
        ctry = {s["id"]: s["country"] for s in t1}
        safe = [sid for sid in t1_ids[1:] if ctry[sid] != "CN" and sid not in self.choke_downstream]
        if len(safe) < 4:  # tiny tenants: allow alternates in any country
            safe = [sid for sid in t1_ids[1:] if sid not in self.choke_downstream]
        qual = []
        for p in parts:
            cur = by_part[p["id"]]
            at_risk = p["id"] in single or cur <= self.choke_downstream
            k = 2 if at_risk else (1 if rng.random() < 0.25 else 0)
            if p["id"] == hero_pid:
                k = 2
            cands = [x for x in safe if x not in cur]
            for sid in rng.sample(cands, min(k, len(cands))):
                qual.append({"supplier_id": sid, "part_id": p["id"],
                             "qualified_on": f"20{rng.randint(23, 26)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                             "lead_time_days": rng.randint(10, 40), "unit_cost": _r(p["unit_cost"] * rng.uniform(1.0, 1.3))})
        self.files["qualified"] = sorted(qual, key=lambda x: (x["part_id"], x["supplier_id"]))
        self.single_sourced = sorted(single)
        self.hero_part = hero_pid
        self.hero_supplier = hero_sid if self.c.tenant == "dataco" else None

    # ---------------------------------------------------------------- people
    def people(self) -> None:
        rng, c = self.rng, self.c
        P = c.p
        teams = [{"id": f"TEAM-{P}{code}", "name": name} for code, name, _, _ in TEAMS]
        scale = c.n_employees / 40
        emps = []
        heroes = list(HEROES) if c.tenant == "dataco" else []
        n = 0
        used = set()
        for code, name, size, roles in TEAMS:
            size = max(1, round(size * scale))
            mine = [h for h in heroes if h[0] == code]
            for i in range(size):
                n += 1
                if i < len(mine):
                    nm, role = mine[i][1], mine[i][2]
                else:
                    while True:
                        nm = self.fake.name() + " [SYNTH]"
                        if nm not in used:
                            break
                    role = rng.choice(roles)
                used.add(nm)
                first_last = nm.replace(" [SYNTH]", "").lower().replace(" ", ".").replace("'", "")
                emps.append({"id": self.pid("EMP", f"{n:03d}"), "name": nm, "role": role, "team_id": f"TEAM-{P}{code}",
                             "contact": f"{first_last}@ripple-demo.example"})
        self.files["teams"] = teams
        self.files["employees"] = emps
        proc = [e["id"] for e in emps if e["team_id"].endswith("PROC")]
        own = []
        for s in self.files["suppliers"]:
            if s["tier"] != 1:
                continue
            if s["id"] == self.hero_supplier:
                own.append({"employee_id": emps[1]["id"], "supplier_id": s["id"], "valid_from": "2021-02-01", "valid_to": "2024-03-01"})
                own.append({"employee_id": emps[0]["id"], "supplier_id": s["id"], "valid_from": "2024-03-01", "valid_to": ""})
                continue
            cur = rng.choice(proc)
            if rng.random() < 0.2:
                past = rng.choice([x for x in proc if x != cur])
                switch = f"20{rng.randint(23, 25)}-{rng.randint(1, 12):02d}-01"
                own.append({"employee_id": past, "supplier_id": s["id"], "valid_from": "2021-01-01", "valid_to": switch})
                own.append({"employee_id": cur, "supplier_id": s["id"], "valid_from": switch, "valid_to": ""})
            else:
                own.append({"employee_id": cur, "supplier_id": s["id"], "valid_from": f"20{rng.randint(20, 24)}-{rng.randint(1, 12):02d}-01", "valid_to": ""})
        self.files["ownership"] = own

    def contracts(self) -> None:
        rng, c = self.rng, self.c
        t1 = [s for s in self.files["suppliers"] if s["tier"] == 1]
        major = [t1[0]] + sorted(t1[1:], key=lambda s: (-s["capacity"], s["id"]))[: c.n_contracts - 1]
        out = []
        for i, s in enumerate(sorted(major, key=lambda s: s["id"])):
            fm = rng.random() < 0.7
            out.append({"id": self.pid("CON", f"{i + 1:04d}"), "supplier_id": s["id"], "start": f"20{rng.randint(22, 24)}-01-01",
                        "end": f"20{rng.randint(27, 29)}-12-31", "sla_days": rng.choice([14, 21, 28, 30, 35, 45]),
                        "penalty_pct": _r(rng.choice([0.5, 0.75, 1.0, 1.5, 2.0]), 2), "penalty_cap_pct": rng.choice([5, 8, 10, 15]),
                        "force_majeure": fm, "exclusivity": rng.random() < 0.15,
                        "doc_id": self.pid("DOC", f"CON-{i + 1:04d}")})
        if c.tenant == "dataco":  # the hero contract: fixed terms the demo talks about
            out[0].update({"sla_days": 21, "penalty_pct": 1.5, "penalty_cap_pct": 10, "force_majeure": True, "exclusivity": False})
        self.files["contracts"] = out

    # ---------------------------------------------------------------- write
    def run(self, out_root: Path | None = None) -> Path:
        self.out_root = out_root or SYNTH_DIR
        products = self.products()
        self.files["products"] = products
        if self.c.tenant == "dataco":
            from ripple.ingest.dataco import order_frame, read_raw

            o = order_frame(read_raw())
            orders = [{"id": f"ORD-{r['Order Id']}", "region": r["region"], "shipping_mode": r["shipping_mode"],
                       "first_product": f"PRD-{r['first_product']}"} for _, r in o.iterrows()]
            del self.files["products"]  # DataCo products come from the raw CSV
        else:
            self.nova_orders(products)
            orders = self.files["orders"]
        self.geography(products)
        self.lanes(orders)
        self.suppliers()
        self.parts_and_bom(products)
        self.supplies()
        self.people()
        self.contracts()
        from ripple.ingest.synth_docs import generate_docs

        generate_docs(self)
        return self.write()

    def write(self) -> Path:
        out = self.out_root / self.c.tenant
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        for name, rows in self.files.items():
            if not rows:
                continue
            cols = list(rows[0].keys())
            with open(out / f"{name}.csv", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
        for name, obj in self.json.items():
            p = out / name
            p.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(obj, str):
                p.write_text(obj)
            else:
                p.write_text(json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
        return out


def generate(tenant: str, out_root: Path | None = None) -> Path:
    return Gen(CFGS[tenant]).run(out_root)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", default="all")
    a = ap.parse_args()
    for t in (CFGS if a.tenant == "all" else [a.tenant]):
        print("wrote", generate(t))


if __name__ == "__main__":
    main()
