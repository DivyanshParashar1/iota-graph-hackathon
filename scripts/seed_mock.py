"""Build a mock tenant to click through, with no LLM calls.

    .venv/bin/python scripts/seed_mock.py                  # into RIPPLE_DB_MODE's database
    .venv/bin/python scripts/seed_mock.py --mode embedded --db var/mock.db

`seed_from_run.py` replays a recorded live run and is the honest demo. This script is for when there is no
recording: it writes a hand-written ontology for a mid-sized footwear maker, a deterministic (seeded) instance
graph of a few hundred nodes, expert roles and a few incoming events, so every screen of the UI has something
to show. Nothing here pretends to be agent output: the tenant is marked `seeded_from="mock"`, the instances are
`confidence="synthetic"`, and the incidents are left at "received" with no Jev decision (only Jev decides).
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ripple.db import TenantScope, close_db, get_db  # noqa: E402
from ripple.experts.store import export_role  # noqa: E402
from ripple.graph.apply import apply_spec, load_instances  # noqa: E402
from ripple.incident import store as incidents  # noqa: E402
from ripple.incident.models import EventRecord  # noqa: E402
from ripple.onboarding import store  # noqa: E402
from ripple.onboarding.models import (  # noqa: E402
    Brief,
    BriefProduct,
    BriefSite,
    BriefSupplier,
    Coverage,
    ExpertRole,
    FormAnswer,
    FormColumn,
    FormField,
    FormSpec,
    IndexSpec,
    InstanceBatch,
    InstanceEdge,
    InstanceNode,
    Message,
    OntologySpec,
    PropertySpec,
    RelationshipSpec,
    TypeDisplay,
    TypeSpec,
)
from ripple.workspace.store import Employee, save_employee  # noqa: E402

COMPANY = "Northwind Footwear"


def P(name, type="string", desc="", unit="", required=False, options=None):  # noqa: A002
    return PropertySpec(name=name, type=type, description=desc, unit=unit, required=required,
                        options=options or [])


def T(label, desc, pattern, icon, color, props, tags, title="name"):
    return TypeSpec(label=label, description=desc, id_pattern=pattern, properties=props, tags=tags,
                    display=TypeDisplay(icon=icon, color=color, title_property=title))


def R(type, frm, to, card, desc, props=None):  # noqa: A002
    return RelationshipSpec.model_validate({"type": type, "from": frm, "to": to, "cardinality": card,
                                            "description": desc, "properties": props or []})


TIERS = ["tier-1", "tier-2", "tier-3"]
RISK = ["low", "medium", "high"]


def spec() -> OntologySpec:
    types = [
        T("Region", "A sourcing or selling region; the unit risk events (port closures, strikes, tariffs) "
          "are reported against.", "REG-###", "globe", "#4C90F0",
          [P("name", required=True, desc="Region name as the planning team uses it"),
           P("continent", "enum", "Continent the region belongs to",
             options=["Asia", "Europe", "North America", "South America", "Africa"]),
           P("risk_index", "float", "Composite geopolitical and logistics risk score, 0 (calm) to 1 (severe)")],
          ["geography"]),
        T("Supplier", "A company that sells Northwind raw materials. Tier-1 suppliers are contracted directly; "
          "tier-2 and tier-3 sit behind them.", "SUP-####", "building", "#2EB67D",
          [P("name", required=True, desc="Legal trading name"),
           P("country", desc="Country of the main production site"),
           P("tier", "enum", "How far upstream the supplier sits", options=TIERS),
           P("lead_time_days", "integer", "Order-to-ship lead time", unit="days"),
           P("on_time_rate", "percent", "Share of POs shipped on the confirmed date, trailing 12 months",
             unit="%"),
           P("risk_rating", "enum", "Supplier-risk team's rating", options=RISK),
           P("annual_spend", "currency", "Northwind's spend with this supplier last fiscal year", unit="USD")],
          ["sourcing", "external"]),
        T("RawMaterial", "A purchased input - leather, mesh, rubber, foam, adhesive or packaging - before it is "
          "cut or moulded into a component.", "RAW-####", "leaf", "#D1980B",
          [P("name", required=True, desc="Material name and grade"),
           P("category", "enum", "Material family", options=["leather", "textile", "rubber", "foam",
                                                              "adhesive", "packaging"]),
           P("unit_cost", "currency", "Average landed cost per purchasing unit", unit="USD"),
           P("purchasing_unit", desc="The unit it is bought in (sq ft, m, kg, sheet)"),
           P("days_of_cover", "integer", "Inventory on hand divided by average daily usage", unit="days")],
          ["sourcing", "inventory"]),
        T("Component", "A made part of a shoe - upper, outsole, midsole, insole, laces - built from raw "
          "materials and assembled into products.", "CMP-####", "gear", "#9D3F9D",
          [P("name", required=True, desc="Component name as on the bill of materials"),
           P("kind", "enum", "Which part of the shoe it is",
             options=["upper", "outsole", "midsole", "insole", "laces", "box"]),
           P("unit_cost", "currency", "Standard cost per pair", unit="USD"),
           P("safety_stock", "integer", "Pairs held as buffer at the plant", unit="pairs")],
          ["bill-of-materials"]),
        T("Plant", "A factory where components are made and shoes are assembled; owned or contract.",
          "PLT-###", "factory", "#E76A6E",
          [P("name", required=True, desc="Plant name"),
           P("city", desc="City"),
           P("country", desc="Country"),
           P("ownership", "enum", "Who runs the plant", options=["owned", "contract"]),
           P("capacity_pairs_per_day", "integer", "Nameplate assembly capacity", unit="pairs/day"),
           P("utilisation", "percent", "Average utilisation over the last 4 weeks", unit="%")],
          ["manufacturing", "site"]),
        T("Product", "A finished shoe style (one SKU family) that Northwind sells.", "PRD-####", "shoe", "#2D72D2",
          [P("name", required=True, desc="Style name"),
           P("line", "enum", "Product line", options=["running", "trail", "lifestyle", "work"]),
           P("sku", "id", "Style-level SKU"),
           P("retail_price", "currency", "Recommended retail price", unit="USD"),
           P("weekly_demand", "integer", "Forecast demand across all channels", unit="pairs/week")],
          ["catalogue"]),
        T("DistributionCenter", "A warehouse that receives finished goods from plants and serves customers in "
          "its region.", "DC-###", "warehouse", "#13C9BA",
          [P("name", required=True, desc="DC name"),
           P("city", desc="City"),
           P("country", desc="Country"),
           P("capacity_pallets", "integer", "Storage capacity", unit="pallets"),
           P("fill_rate", "percent", "Order lines shipped complete, last 4 weeks", unit="%")],
          ["logistics", "site"]),
        T("Carrier", "A logistics provider that moves shipments between plants and distribution centres.",
          "CAR-###", "truck", "#F0B726",
          [P("name", required=True, desc="Carrier name"),
           P("mode", "enum", "Main transport mode", options=["ocean", "air", "road", "rail"]),
           P("on_time_rate", "percent", "Shipments delivered within the promised window", unit="%")],
          ["logistics", "external"]),
        T("Shipment", "One booked movement of finished goods from a plant to a distribution centre.",
          "SHP-#####", "package", "#D69FD6",
          [P("reference", required=True, desc="Booking reference"),
           P("status", "enum", "Where the shipment is", options=["booked", "in_transit", "delayed",
                                                                   "delivered"]),
           P("eta", "date", "Estimated arrival at the destination DC"),
           P("pairs", "integer", "Pairs on board", unit="pairs"),
           P("value", "currency", "Goods value at cost", unit="USD")],
          ["logistics", "transactional"], title="reference"),
        T("Customer", "A wholesale account, retail partner or Northwind's own e-commerce channel.", "CUS-####",
          "user", "#72CA9B",
          [P("name", required=True, desc="Account name"),
           P("channel", "enum", "How the customer buys", options=["wholesale", "retail", "ecommerce"]),
           P("country", desc="Country"),
           P("annual_revenue", "currency", "Northwind revenue from this account last fiscal year", unit="USD"),
           P("service_level", "percent", "Contracted on-time-in-full target", unit="%")],
          ["demand", "external"]),
    ]
    rels = [
        R("BASED_IN", "Supplier", "Region", "many-to-one", "The region the supplier's main site is in."),
        R("SUPPLIES", "Supplier", "RawMaterial", "many-to-many",
          "The supplier is an approved source for the material.",
          [P("price", "currency", "Contract price per purchasing unit", unit="USD"),
           P("share", "percent", "Share of Northwind's volume of this material", unit="%")]),
        R("USED_IN", "RawMaterial", "Component", "many-to-many", "The material is consumed making the component.",
          [P("qty_per_pair", "float", "Quantity consumed per pair")]),
        R("SUBSTITUTES", "Component", "Component", "many-to-many",
          "The component can replace the other one on the line without re-certification."),
        R("PART_OF", "Component", "Product", "many-to-many", "The component is on the product's bill of materials."),
        R("MAKES", "Plant", "Component", "many-to-many", "The plant produces the component in-house."),
        R("ASSEMBLES", "Plant", "Product", "many-to-many", "The plant assembles the finished product.",
          [P("share", "percent", "Share of the product's volume made at this plant", unit="%")]),
        R("SITED_IN", "Plant", "Region", "many-to-one", "The region the plant is in."),
        R("DEPARTS_FROM", "Shipment", "Plant", "many-to-one", "The plant the shipment was loaded at."),
        R("DESTINED_FOR", "Shipment", "DistributionCenter", "many-to-one", "The DC the shipment is going to."),
        R("CARRIED_BY", "Shipment", "Carrier", "many-to-one", "The carrier moving the shipment."),
        R("CONTAINS", "Shipment", "Product", "many-to-many", "Products on board.",
          [P("pairs", "integer", "Pairs of this product on board", unit="pairs")]),
        R("OPERATES_IN", "DistributionCenter", "Region", "many-to-one", "The region the DC is in."),
        R("SERVES", "DistributionCenter", "Customer", "one-to-many", "The DC ships the customer's orders."),
        R("ORDERS", "Customer", "Product", "many-to-many", "The customer buys the product regularly.",
          [P("weekly_pairs", "integer", "Average weekly order", unit="pairs/week")]),
        R("CONTRACTED_FOR", "Carrier", "Region", "many-to-many", "The carrier has a rate contract in the region."),
    ]
    indexes = [IndexSpec(label=t.label, property="name") for t in types if t.label != "Shipment"]
    indexes.append(IndexSpec(label="Shipment", property="status"))
    return OntologySpec(
        version=1, types=types, relationships=rels, indexes=indexes,
        rationale=(
            "Northwind's disruptions start upstream (a leather tannery, a rubber compound plant) and land "
            "downstream as late shipments to wholesale accounts, so the model follows the physical flow end to "
            "end: Supplier -> RawMaterial -> Component -> Product, made at Plants, moved as Shipments by "
            "Carriers to DistributionCenters that serve Customers. Region is a separate type because the team "
            "reports risk (port closures, strikes, tariffs) per region, and it lets one event fan out to every "
            "supplier, plant and DC exposed to it. SUBSTITUTES captures approved alternates so a shortage can "
            "be answered with a swap rather than a stop."),
        coverage=Coverage(
            assumed=["Lead times are supplier-quoted, not measured",
                     "One plant per shipment (no consolidation hubs)",
                     "Customer demand is a weekly average, not order lines"],
            unmapped_answers=["Payment terms per supplier", "Retail store-level inventory"]))


CITIES = {
    "REG-001": ("Southeast Asia", "Asia", [("Ho Chi Minh City", "Vietnam"), ("Jakarta", "Indonesia")]),
    "REG-002": ("South China", "Asia", [("Dongguan", "China"), ("Guangzhou", "China")]),
    "REG-003": ("South Asia", "Asia", [("Chennai", "India"), ("Dhaka", "Bangladesh")]),
    "REG-004": ("Southern Europe", "Europe", [("Porto", "Portugal"), ("Florence", "Italy")]),
    "REG-005": ("Northern Europe", "Europe", [("Rotterdam", "Netherlands"), ("Hamburg", "Germany")]),
    "REG-006": ("US East", "North America", [("Newark", "USA"), ("Atlanta", "USA")]),
    "REG-007": ("US West", "North America", [("Los Angeles", "USA"), ("Reno", "USA")]),
    "REG-008": ("Brazil", "South America", [("Novo Hamburgo", "Brazil"), ("Franca", "Brazil")]),
}
SOURCING = ["REG-001", "REG-002", "REG-003", "REG-004", "REG-008"]
SELLING = ["REG-005", "REG-006", "REG-007"]

MATERIALS = {
    "leather": ["Full-grain cowhide", "Nubuck", "Suede split", "Chrome-free leather"],
    "textile": ["Engineered mesh", "Recycled polyester knit", "Canvas 12oz", "Cordura ripstop", "Lining tricot"],
    "rubber": ["Carbon rubber compound", "Gum rubber", "Recycled rubber blend", "Vibram-grade compound"],
    "foam": ["EVA pellets", "PU foam", "Supercritical TPEE", "Memory foam sheet"],
    "adhesive": ["Water-based PU cement", "Hot-melt adhesive", "Primer UV-2"],
    "packaging": ["Kraft shoebox", "Tissue paper", "Shipping carton 12-pair"],
}
SUPPLIER_NAMES = [
    "Saigon Tannery Co", "Pou Chen Materials", "Dongguan Rubber Works", "Feng Tay Textiles", "Chennai Leather Ltd",
    "Dhaka Mesh Mills", "Porto Couros", "Toscana Pelle", "Novo Componentes", "Franca Solados",
    "Jakarta Foam Industries", "Guangzhou Adhesives", "Mekong Packaging", "Asia Pacific Polymers", "Bengal Canvas",
    "Lusitania Laces", "Rio Grande Rubber", "Hanoi Knitworks", "Pearl River EVA", "Coromandel Hides",
    "Sao Paulo Packaging", "Shenzhen TPU", "Binh Duong Box Co", "Kerala Natural Rubber", "Emilia Primers",
    "Surabaya Insoles", "Zhejiang Eyelets", "Chittagong Threads",
]
PRODUCT_NAMES = {
    "running": ["Tempo 4", "Glide Pro", "Pacer", "Strider Elite", "Velocity 2", "Daily Trainer", "Racer Flat"],
    "trail": ["Ridge GTX", "Summit Trail", "Canyon 3", "Scree Runner", "Alpine Hiker"],
    "lifestyle": ["Court Classic", "Harbor Slip-on", "Metro Low", "Heritage 77", "Canvas Deck", "Loafer One"],
    "work": ["Foreman Boot", "Site Safety S3", "Warehouse Pro", "Chef Clog"],
}
CARRIERS = [("Maersk Line", "ocean"), ("CMA CGM", "ocean"), ("Hapag-Lloyd", "ocean"), ("DHL Global Forwarding",
            "air"), ("Kuehne+Nagel", "air"), ("XPO Logistics", "road"), ("J.B. Hunt", "road"),
            ("DB Cargo", "rail"), ("Flexport", "ocean")]
CUSTOMERS = [
    ("Foot Locker", "retail"), ("JD Sports", "retail"), ("Zalando", "ecommerce"), ("REI", "retail"),
    ("Dick's Sporting Goods", "retail"), ("Nordstrom", "retail"), ("Amazon Fashion", "ecommerce"),
    ("Northwind.com", "ecommerce"), ("Intersport", "wholesale"), ("Decathlon", "wholesale"),
    ("Sportsman's Warehouse", "retail"), ("Academy Sports", "retail"), ("Footasylum", "retail"),
    ("Galeria", "wholesale"), ("El Corte Ingles", "wholesale"), ("Scheels", "retail"),
    ("Running Warehouse", "ecommerce"), ("Work Boot Depot", "wholesale"), ("Bergfreunde", "ecommerce"),
    ("Snipes", "retail"), ("Size?", "retail"), ("Big 5", "retail"),
]


def instances(rng: random.Random, forms: dict[str, list[str]]) -> InstanceBatch:
    nodes: list[InstanceNode] = []
    edges: list[InstanceEdge] = []

    def node(label, nid, src_key=None, **props):
        sources = []
        if src_key and forms.get(src_key):
            sources = [rng.choice(forms[src_key])]
        nodes.append(InstanceNode(label=label, id=nid, properties=props, source_ids=sources,
                                  confidence="synthetic"))
        return nid

    def edge(t, a, b, **props):
        edges.append(InstanceEdge.model_validate({"type": t, "from": a, "to": b, "properties": props}))

    for rid, (name, cont, _) in CITIES.items():
        node("Region", rid, name=name, continent=cont, risk_index=round(rng.uniform(0.1, 0.8), 2))

    suppliers = []
    for i, name in enumerate(SUPPLIER_NAMES, 1):
        rid = rng.choice(SOURCING)
        city, country = rng.choice(CITIES[rid][2])
        sid = node("Supplier", f"SUP-{i:04d}", "suppliers", name=name, country=country,
                   tier=rng.choices(TIERS, [5, 3, 1])[0], lead_time_days=rng.randint(14, 75),
                   on_time_rate=round(rng.uniform(72, 99), 1), risk_rating=rng.choices(RISK, [5, 3, 1])[0],
                   annual_spend=rng.randint(200, 9000) * 1000)
        edge("BASED_IN", sid, rid)
        suppliers.append(sid)

    materials = []
    units = {"leather": "sq ft", "textile": "m", "rubber": "kg", "foam": "kg", "adhesive": "kg",
             "packaging": "unit"}
    k = 0
    for cat, names in MATERIALS.items():
        for name in names:
            k += 1
            mid = node("RawMaterial", f"RAW-{k:04d}", "materials", name=name, category=cat,
                       unit_cost=round(rng.uniform(0.1, 12), 2), purchasing_unit=units[cat],
                       days_of_cover=rng.randint(4, 60))
            materials.append((mid, cat))
            for sid in rng.sample(suppliers, rng.randint(1, 3)):
                edge("SUPPLIES", sid, mid, price=round(rng.uniform(0.1, 12), 2),
                     share=rng.choice([100, 70, 60, 50, 40, 30]))

    supplying = {e.from_id for e in edges if e.type == "SUPPLIES"}
    for sid in suppliers:
        if sid not in supplying:
            for mid, _ in rng.sample(materials, rng.randint(1, 2)):
                edge("SUPPLIES", sid, mid, price=round(rng.uniform(0.1, 12), 2), share=rng.choice([40, 30, 20]))

    comp_kinds = {"upper": ["leather", "textile"], "outsole": ["rubber"], "midsole": ["foam"],
                  "insole": ["foam", "textile"], "laces": ["textile"], "box": ["packaging"]}
    components: dict[str, list[str]] = {}
    k = 0
    for kind, cats in comp_kinds.items():
        n = {"upper": 12, "outsole": 8, "midsole": 6, "insole": 5, "laces": 4, "box": 2}[kind]
        for j in range(n):
            k += 1
            cid = node("Component", f"CMP-{k:04d}", "bom", name=f"{kind.capitalize()} {chr(65 + j)}-{k:02d}",
                       kind=kind, unit_cost=round(rng.uniform(0.2, 14), 2), safety_stock=rng.randint(500, 8000))
            components.setdefault(kind, []).append(cid)
            pool = [m for m, c in materials if c in cats]
            for mid in rng.sample(pool, min(len(pool), rng.randint(1, 3))):
                edge("USED_IN", mid, cid, qty_per_pair=round(rng.uniform(0.05, 1.8), 2))
            adhesive = [m for m, c in materials if c == "adhesive"]
            if kind in ("outsole", "midsole", "upper"):
                edge("USED_IN", rng.choice(adhesive), cid, qty_per_pair=0.02)
    for ids in components.values():
        for a in ids:
            if rng.random() < 0.35 and len(ids) > 1:
                b = rng.choice([x for x in ids if x != a])
                edge("SUBSTITUTES", a, b)

    plants = []
    plant_specs = [("Binh Duong Assembly", "REG-001", "contract"), ("Dongguan Factory 3", "REG-002", "contract"),
                   ("Chennai Works", "REG-003", "contract"), ("Porto Atelier", "REG-004", "owned"),
                   ("Novo Hamburgo Plant", "REG-008", "owned"), ("Jakarta Line 2", "REG-001", "contract")]
    for i, (name, rid, own) in enumerate(plant_specs, 1):
        city, country = CITIES[rid][2][0]
        pid = node("Plant", f"PLT-{i:03d}", "sites", name=name, city=city, country=country, ownership=own,
                   capacity_pairs_per_day=rng.choice([4000, 6000, 9000, 12000, 15000]),
                   utilisation=round(rng.uniform(62, 97), 1))
        edge("SITED_IN", pid, rid)
        plants.append(pid)
        for kind in rng.sample(list(components), 3):
            for cid in rng.sample(components[kind], min(3, len(components[kind]))):
                edge("MAKES", pid, cid)

    products = []
    k = 0
    for line, names in PRODUCT_NAMES.items():
        for name in names:
            k += 1
            prid = node("Product", f"PRD-{k:04d}", "catalogue", name=name, line=line, sku=f"NW-{line[:2].upper()}"
                        f"-{1000 + k}", retail_price=rng.choice([79, 99, 119, 129, 149, 169, 189, 219]),
                        weekly_demand=rng.randint(300, 6000))
            products.append(prid)
            for kind in ("upper", "outsole", "midsole", "insole", "laces", "box"):
                if kind == "midsole" and line == "work" and rng.random() < 0.5:
                    continue
                edge("PART_OF", rng.choice(components[kind]), prid)
            for pid in rng.sample(plants, rng.randint(1, 2)):
                edge("ASSEMBLES", pid, prid, share=rng.choice([100, 60, 40]))

    dcs = []
    dc_specs = [("Rotterdam DC", "REG-005"), ("Hamburg DC", "REG-005"), ("Newark DC", "REG-006"),
                ("Atlanta DC", "REG-006"), ("Los Angeles DC", "REG-007"), ("Reno Fulfilment", "REG-007")]
    for i, (name, rid) in enumerate(dc_specs, 1):
        city, country = next((c for c in CITIES[rid][2] if c[0] in name), CITIES[rid][2][0])
        did = node("DistributionCenter", f"DC-{i:03d}", "sites", name=name, city=city, country=country,
                   capacity_pallets=rng.choice([8000, 12000, 20000, 30000]),
                   fill_rate=round(rng.uniform(88, 99.5), 1))
        edge("OPERATES_IN", did, rid)
        dcs.append((did, rid))

    carriers = []
    for i, (name, mode) in enumerate(CARRIERS, 1):
        cid = node("Carrier", f"CAR-{i:03d}", "logistics", name=name, mode=mode,
                   on_time_rate=round(rng.uniform(78, 98), 1))
        carriers.append(cid)
        for rid in rng.sample(list(CITIES), rng.randint(2, 4)):
            edge("CONTRACTED_FOR", cid, rid)

    for i, (name, channel) in enumerate(CUSTOMERS, 1):
        did, rid = dcs[(i - 1) % len(dcs)]
        cus = node("Customer", f"CUS-{i:04d}", "customers", name=name, channel=channel,
                   country=CITIES[rid][2][0][1], annual_revenue=rng.randint(500, 40000) * 1000,
                   service_level=rng.choice([95, 97, 98, 99]))
        edge("SERVES", did, cus)
        for prid in rng.sample(products, rng.randint(3, 8)):
            edge("ORDERS", cus, prid, weekly_pairs=rng.randint(20, 900))

    for i in range(1, 121):
        pid = rng.choice(plants)
        did, _ = rng.choice(dcs)
        status = rng.choices(["booked", "in_transit", "delayed", "delivered"], [2, 5, 1, 4])[0]
        pairs = rng.randint(2, 30) * 600
        shp = node("Shipment", f"SHP-{i:05d}", "logistics", reference=f"NW{24000 + i * 7}",
                   status=status, eta=f"2026-{rng.randint(10, 12)}-{rng.randint(1, 28):02d}", pairs=pairs,
                   value=pairs * rng.randint(14, 38))
        edge("DEPARTS_FROM", shp, pid)
        edge("DESTINED_FOR", shp, did)
        edge("CARRIED_BY", shp, rng.choice(carriers))
        for prid in rng.sample(products, rng.randint(1, 4)):
            edge("CONTAINS", shp, prid, pairs=rng.randint(1, 10) * 300)

    return InstanceBatch(nodes=nodes, edges=edges, notes="mock data from scripts/seed_mock.py")


def brief() -> Brief:
    return Brief(
        company=COMPANY, industry="Footwear",
        summary="Mid-sized maker of running, trail, lifestyle and work shoes. Six plants (two owned, four "
                "contract) in Asia, Europe and Brazil; six DCs in Europe and the US; about 2.4M pairs a year.",
        products=[BriefProduct(name=n, components=["upper", "outsole", "midsole", "insole", "laces", "box"],
                               markets=["EU", "US"]) for n in ("Tempo 4", "Ridge GTX", "Court Classic")],
        suppliers=[BriefSupplier(kind="tier-1 leather", name="Saigon Tannery Co", country="Vietnam"),
                   BriefSupplier(kind="outsole rubber", name="Dongguan Rubber Works", country="China")],
        sites=[BriefSite(kind="factory", name="Porto Atelier", location="Porto, Portugal"),
               BriefSite(kind="distribution centre", name="Rotterdam DC", location="Rotterdam, Netherlands")],
        transport_modes=["ocean", "air", "road", "rail"],
        customers=["Foot Locker", "Zalando", "REI", "Northwind.com"], markets=["EU", "US"],
        risks=["Single-sourced leather grades", "Trans-Pacific ocean delays", "Rubber price swings"],
        pains=["Late wholesale deliveries in peak season", "No view of tier-2 suppliers"],
        scale="~USD 380M revenue, 2.4M pairs/year")


def roles() -> list[ExpertRole]:
    return [
        ExpertRole(name="sourcing_risk", title="Sourcing Risk Analyst",
                   mandate="Watches supplier and material exposure and finds alternates before a shortage bites.",
                   justification="Leather and rubber are single- or dual-sourced (Supplier-SUPPLIES-RawMaterial) "
                                 "and regional events hit many suppliers at once (BASED_IN Region).",
                   focus_types=["Supplier", "RawMaterial", "Region", "Component"],
                   focus_relationships=["SUPPLIES", "BASED_IN", "USED_IN", "SUBSTITUTES"],
                   playbook=["Which products depend on a single supplier?",
                             "What is exposed if a region goes offline?"],
                   tools=["describe_ontology", "find_nodes", "get_node", "neighbours", "aggregate"],
                   status="approved"),
        ExpertRole(name="production_planner", title="Production Planner",
                   mandate="Balances plant capacity against demand and re-plans when a component is short.",
                   justification="Products are assembled at one or two Plants (ASSEMBLES) from Components the "
                                 "plants make (MAKES), so a shortage is a re-plan across plants.",
                   focus_types=["Plant", "Component", "Product"],
                   focus_relationships=["MAKES", "ASSEMBLES", "PART_OF"],
                   playbook=["Which plant has headroom for this style?"],
                   tools=["describe_ontology", "find_nodes", "get_node", "neighbours", "aggregate"],
                   status="approved"),
        ExpertRole(name="logistics_controller", title="Logistics Controller",
                   mandate="Tracks shipments in flight and proposes reroutes or mode changes when one slips.",
                   justification="Shipments move Plant -> DistributionCenter via Carriers (DEPARTS_FROM, "
                                 "DESTINED_FOR, CARRIED_BY) and carry the customer impact of any delay.",
                   focus_types=["Shipment", "Carrier", "DistributionCenter", "Plant"],
                   focus_relationships=["DEPARTS_FROM", "DESTINED_FOR", "CARRIED_BY", "CONTAINS"],
                   playbook=["Which delayed shipments carry top-customer products?"],
                   tools=["describe_ontology", "find_nodes", "get_node", "neighbours", "aggregate"],
                   status="approved"),
        ExpertRole(name="customer_service_lead", title="Customer Service Lead",
                   mandate="Knows which accounts are hurt by a delay and drafts what to tell them.",
                   justification="Customers are served by one DC (SERVES) and order specific products (ORDERS), "
                                 "so a late shipment maps to named accounts and their service levels.",
                   focus_types=["Customer", "DistributionCenter", "Product"],
                   focus_relationships=["SERVES", "ORDERS"],
                   playbook=["Who misses their service level if this DC is short?"],
                   tools=["describe_ontology", "find_nodes", "get_node", "neighbours"],
                   status="approved"),
    ]


def seed_forms(scope: TenantScope, sid: str) -> dict[str, list[str]]:
    """A data pack the instances can point their provenance at: one submitted form with a few answers."""
    groups = {"suppliers": "Suppliers and what they sell", "materials": "Raw materials", "bom": "Bill of materials",
              "sites": "Plants and distribution centres", "catalogue": "Product catalogue",
              "logistics": "Carriers and open shipments", "customers": "Top customers"}
    fields = [FormField(id=k, label=v, type="group", fields=[FormColumn(id="name", label="Name")])
              for k, v in groups.items()]
    form = store.save_form(scope, FormSpec(title="Round 1 - your network", fields=fields, status="submitted"))
    out: dict[str, list[str]] = {}
    for k in groups:
        ans = store.save_answer(scope, FormAnswer(form_id=form.id, field_id=k, value=[{"name": f"{k} sheet"}],
                                                  source="file", confidence="ballpark"))
        out[k] = [ans.id]
    store.append_message(scope, sid, Message(role="user", stage="data", kind="form", text=f"Submitted {form.title}.",
                                             payload={"form_id": form.id}))
    return out


EVENTS = [
    ("port_closure", "Typhoon closes Ho Chi Minh City port (Cat Lai) for an estimated 72 hours",
     {"region": "REG-001", "expected_hours": 72}, ["REG-001", "PLT-001", "PLT-006"]),
    ("supplier_delay", "Saigon Tannery Co reports a 3-week delay on full-grain cowhide after a wastewater "
     "inspection", {"supplier": "SUP-0001", "material": "RAW-0001", "delay_days": 21}, ["SUP-0001", "RAW-0001"]),
    ("carrier_disruption", "Maersk Line blank sailing: next two Asia-Europe loops cancelled",
     {"carrier": "CAR-001", "loops": 2}, ["CAR-001"]),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tenant", default="northwind_footwear")
    ap.add_argument("--mode", default=None, help="embedded | remote (default: RIPPLE_DB_MODE)")
    ap.add_argument("--db", default=None, help="embedded database file (default: RIPPLE_DB_PATH)")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    db = get_db(Path(a.db) if a.db else None, mode=a.mode)
    try:
        scope = TenantScope(a.tenant, db)
        scope.drop()
        store.create_tenant(scope, COMPANY, "Footwear")
        store.set_tenant(scope, seeded_from="mock")
        sid = store.create_session(scope, "mock", "seed_mock")["id"]
        print(f"tenant {a.tenant} ({db.mode})")

        store.append_message(scope, sid, Message(role="agent", agent="interviewer", stage="interview",
                                                 text="(mock tenant - no interview was run)"))
        forms = seed_forms(scope, sid)
        store.put_brief(scope, brief(), approved=True)

        s = spec()
        row = store.save_spec(scope, s, status="draft", rationale=s.rationale)
        store.set_spec_status(scope, row["id"], "approved")
        applied = apply_spec(scope, s)
        print(f"  ontology v{row['version']}: {applied['types']} types, {applied['relationships']} relationships")
        batch = instances(random.Random(a.seed), forms)
        loaded = load_instances(scope, s, batch, wipe=True)
        print(f"  instances: {loaded['nodes']} nodes, {loaded['edges']} edges, {loaded['provenance']} provenance")

        for r in roles():
            export_role(scope, store.save_expert(scope, r))
        print(f"  experts: {', '.join(r.title for r in roles())}")

        people = [("Maya Chen", "Head of Logistics", ["logistics_controller", "customer_service_lead"]),
                  ("Arjun Mehta", "Sourcing Manager", ["sourcing_risk"]),
                  ("Sofia Rossi", "Plant Operations Lead", ["production_planner"])]
        for name, title, names in people:
            save_employee(scope, Employee(name=name, title=title, role_ids=[f"EXP-{n}" for n in names]))
        print(f"  employees: {', '.join(p[0] for p in people)}")

        for kind, summary, raw, concerns in EVENTS:
            inc = incidents.create_incident(scope, EventRecord(kind=kind, summary=summary, source="mock", raw=raw))
            incidents.link_concerns(scope, inc["id"], concerns)
        print(f"  incidents: {len(EVENTS)} received events (not run through the pipeline)")

        store.set_session(scope, sid, stage="ready")
        store.set_tenant(scope, stage="ready", status="live")
        c = store.counts(scope)
        print(f"  graph: {c['nodes']} nodes, {c['edges']} edges")
    finally:
        db.save()
        close_db(db)


if __name__ == "__main__":
    main()
