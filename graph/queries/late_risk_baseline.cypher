// name: late_risk_baseline
// purpose: Q5. Historical late-delivery rate (DataCo Late_delivery_risk labels) for a shipping mode and market.
// kind: read
// params: {"mode": "Standard Class", "market": "Europe"}
MATCH (o:Order)-[:SHIPS_VIA]->(l:Lane)
WHERE l.mode = $mode AND o.market = $market
RETURN avg(o.late_risk) AS late_rate, count(o) AS sample
