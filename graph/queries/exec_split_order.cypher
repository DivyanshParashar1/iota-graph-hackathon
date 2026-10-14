// name: exec_split_order
// purpose: Action effect SPLIT_ORDER: create a child Order on another lane carrying a fraction of the value.
// kind: write
// params: {"aid": "ACT-example", "oid": "ORD-NONE", "child": "ORD-NONE-S1", "to_lane": "LANE-X", "fraction": 0.5}
MATCH (o:Order {id: $oid})-[:PLACED_BY]->(c:Customer)
MATCH (nl:Lane {id: $to_lane})
CREATE (k:Order {id: $child, status: o.status, open: o.open, region: o.region, market: o.market, country: o.country,
                 city: o.city, date: o.date, late_risk: o.late_risk, days_sched: o.days_sched, shipping_mode: nl.mode,
                 total: round(o.total * $fraction * 100) / 100.0, profit: 0.0, split_by: $aid})
CREATE (k)-[:SPLIT_FROM]->(o)
CREATE (k)-[:PLACED_BY]->(c)
CREATE (k)-[:SHIPS_VIA]->(nl)
SET o.total = round(o.total * (1 - $fraction) * 100) / 100.0
RETURN k.id AS child
