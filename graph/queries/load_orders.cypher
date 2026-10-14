// name: load_orders
// purpose: Ingest. Upsert orders with PLACED_BY, IN_MARKET and IN_REGION edges.
// kind: write
// params: {"rows": [{"id": "ORD-TEST", "date": "2017-01-01T00:00", "status": "PENDING", "open": true, "region": "Test", "market": "Test", "country": "X", "city": "Y", "total": 1.0, "profit": 0.1, "late_risk": 0, "delivery_status": "Late delivery", "days_real": 3, "days_sched": 2, "shipping_mode": "Standard Class", "customer_id": "CUS-TEST", "market_id": "MKT-Test", "region_id": "REG-test"}]}
UNWIND $rows AS r
MERGE (o:Order {id: r.id})
SET o.date = r.date, o.status = r.status, o.open = r.open, o.region = r.region, o.market = r.market,
    o.country = r.country, o.city = r.city, o.total = r.total, o.profit = r.profit, o.late_risk = r.late_risk,
    o.delivery_status = r.delivery_status, o.days_real = r.days_real, o.days_sched = r.days_sched,
    o.shipping_mode = r.shipping_mode
WITH o, r
MATCH (c:Customer {id: r.customer_id})
MATCH (m:Market {id: r.market_id})
MATCH (g:Region {id: r.region_id})
MERGE (o)-[:PLACED_BY]->(c)
MERGE (o)-[:IN_MARKET]->(m)
MERGE (o)-[:IN_REGION]->(g)
