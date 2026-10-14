// name: load_suppliers
// purpose: Ingest. Upsert synthetic suppliers (RiskBearing), Supplier-[:SHIPS_FROM]->Port.
// kind: write
// params: {"rows": [{"id": "SUP-TEST", "name": "Test [SYNTH]", "tier": 1, "country": "XX", "lat": 0.0, "lon": 0.0, "port_id": "PORT-TEST", "capacity": 100, "reliability": 0.9, "risk_score": 0.2}]}
UNWIND $rows AS r
MERGE (s:Supplier {id: r.id})
SET s:RiskBearing, s.name = r.name, s.tier = r.tier, s.country = r.country, s.lat = r.lat, s.lon = r.lon,
    s.capacity = r.capacity, s.reliability = r.reliability, s.risk_score = r.risk_score, s.synthetic = true,
    s.status = 'active'
WITH s, r
MATCH (p:Port {id: r.port_id})
MERGE (s)-[:SHIPS_FROM]->(p)
