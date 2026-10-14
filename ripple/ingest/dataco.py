"""DataCo CSV.gz -> Orders, OrderLines, Products, Customers, Markets, Regions.

PII columns (names, emails, passwords, streets, zip codes, coordinates) are never read: `usecols` drops them
at read time. Revenue is `Sales` (pre-discount); Order.total = round(sum(Sales of its items), 2). The same
definitions are used by eval/ground_truth.py.
"""

from __future__ import annotations

import re
import time
from functools import lru_cache

import pandas as pd

from ripple import ROOT
from ripple.db import TenantScope

RAW = ROOT / "data" / "raw" / "DataCoSupplyChainDataset.csv.gz"
OPEN_STATUSES = ("PENDING", "PROCESSING", "PENDING_PAYMENT", "ON_HOLD", "PAYMENT_REVIEW")
PII_COLUMNS = ("Customer Email", "Customer Fname", "Customer Lname", "Customer Password", "Customer Street",
               "Customer Zipcode", "Order Zipcode", "Latitude", "Longitude", "Product Image", "Product Description")
USECOLS = [
    "Order Id", "Order Item Id", "order date (DateOrders)", "Order Status", "Order Region", "Order Country",
    "Order City", "Market", "Order Item Quantity", "Sales", "Order Item Product Price", "Order Profit Per Order",
    "Product Card Id", "Product Name", "Product Price", "Category Name", "Department Name", "Shipping Mode",
    "Days for shipping (real)", "Days for shipment (scheduled)", "Delivery Status", "Late_delivery_risk",
    "Order Customer Id", "Customer Segment", "Customer City", "Customer State", "Customer Country",
]
BATCH = 5000


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


@lru_cache
def _read_raw_cached() -> pd.DataFrame:
    df = pd.read_csv(RAW, encoding="latin-1", usecols=USECOLS)
    df["Order Region"] = df["Order Region"].str.strip()
    return df


def read_raw() -> pd.DataFrame:
    """The DataCo item rows (non-PII columns only). Returns a copy."""
    return _read_raw_cached().copy()


def order_frame(df: pd.DataFrame) -> pd.DataFrame:
    """One row per order. total = round(sum(Sales), 2)."""
    g = df.sort_values("Order Item Id").groupby("Order Id", sort=True)
    o = g.agg(
        date=("order date (DateOrders)", "first"), status=("Order Status", "first"), region=("Order Region", "first"),
        market=("Market", "first"), country=("Order Country", "first"), city=("Order City", "first"),
        total=("Sales", "sum"), profit=("Order Profit Per Order", "sum"), late_risk=("Late_delivery_risk", "max"),
        delivery_status=("Delivery Status", "first"), days_real=("Days for shipping (real)", "first"),
        days_sched=("Days for shipment (scheduled)", "first"), shipping_mode=("Shipping Mode", "first"),
        customer=("Order Customer Id", "first"), first_product=("Product Card Id", "first"),
    ).reset_index()
    o["total"] = o["total"].round(2)
    o["profit"] = o["profit"].round(2)
    o["open"] = o["status"].isin(OPEN_STATUSES)
    return o


def _iso(s: str) -> str:
    return pd.to_datetime(s, format="%m/%d/%Y %H:%M").strftime("%Y-%m-%dT%H:%M")


def _batches(rows: list[dict], n: int = BATCH):
    for i in range(0, len(rows), n):
        yield rows[i : i + n]


def load_dataco(scope: TenantScope, order_ids: list[int] | None = None) -> dict:
    """Load DataCo (optionally only the given Order Ids) into the tenant's ops graph."""
    t0 = time.time()
    df = read_raw()
    if order_ids is not None:
        df = df[df["Order Id"].isin(set(order_ids))]
    g = scope.ops

    # Every product is loaded even in a sample, so the synthetic BOM always has its targets.
    allp = read_raw().drop_duplicates("Product Card Id").sort_values("Product Card Id")
    rows = [{"id": f"PRD-{r['Product Card Id']}", "name": r["Product Name"], "category": r["Category Name"],
             "department": r["Department Name"], "price": float(r["Product Price"])} for _, r in allp.iterrows()]
    g.run("load_products", {"rows": rows})

    mr = df.drop_duplicates("Order Region")[["Market", "Order Region"]]
    g.run("load_regions", {"rows": [{"market_id": f"MKT-{slug(m)}", "market": m, "region_id": f"REG-{slug(r)}", "region": r}
                                    for m, r in mr.itertuples(index=False)]})

    cust = df.drop_duplicates("Order Customer Id")
    crow = [{"id": f"CUS-{r['Order Customer Id']}", "segment": r["Customer Segment"], "city": r["Customer City"],
             "state": r["Customer State"], "country": r["Customer Country"]} for _, r in cust.iterrows()]
    for b in _batches(crow):
        g.run("load_customers", {"rows": b})

    o = order_frame(df)
    dates = {d: _iso(d) for d in o["date"].unique()}
    orow = [{
        "id": f"ORD-{r.Index}", "date": dates[r.date], "status": r.status, "open": bool(r.open), "region": r.region,
        "market": r.market, "country": r.country, "city": r.city, "total": float(r.total), "profit": float(r.profit),
        "late_risk": int(r.late_risk), "delivery_status": r.delivery_status, "days_real": int(r.days_real),
        "days_sched": int(r.days_sched), "shipping_mode": r.shipping_mode, "customer_id": f"CUS-{r.customer}",
        "market_id": f"MKT-{slug(r.market)}", "region_id": f"REG-{slug(r.region)}",
    } for r in o.set_index("Order Id").itertuples()]
    for b in _batches(orow):
        g.run("load_orders", {"rows": b})

    lrow = [{"id": f"OL-{r[0]}", "order_id": f"ORD-{r[1]}", "product_id": f"PRD-{r[2]}", "qty": int(r[3]),
             "total": round(float(r[4]), 2), "price": float(r[5])}
            for r in df[["Order Item Id", "Order Id", "Product Card Id", "Order Item Quantity", "Sales",
                         "Order Item Product Price"]].itertuples(index=False)]
    for b in _batches(lrow):
        g.run("load_order_lines", {"rows": b})
    return {"products": len(rows), "customers": len(crow), "orders": len(orow), "lines": len(lrow),
            "seconds": round(time.time() - t0, 2)}
