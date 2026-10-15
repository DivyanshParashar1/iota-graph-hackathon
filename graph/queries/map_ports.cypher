// name: map_ports
// purpose: Map layer: ports with coordinates, status and risk.
// kind: read
// params: {}
MATCH (p:Port)
OPTIONAL MATCH (d:Disruption {active: true})-[:AFFECTS]->(p)
RETURN p.id AS id, p.name AS name, p.country AS country, p.lat AS lat, p.lon AS lon, p.status AS status,
       p.risk_score AS risk_score, collect(d.id) AS disruptions
