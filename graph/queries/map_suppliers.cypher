// name: map_suppliers
// purpose: Map layer: suppliers with coordinates, tier, risk and status.
// kind: read
// params: {}
MATCH (s:Supplier)
OPTIONAL MATCH (d:Disruption {active: true})-[:AFFECTS]->(s)
RETURN s.id AS id, s.name AS name, s.tier AS tier, s.country AS country, s.lat AS lat, s.lon AS lon,
       s.risk_score AS risk_score, s.status AS status, collect(d.id) AS disruptions
