// name: load_ports
// purpose: Ingest. Upsert real ports (RiskBearing).
// kind: write
// params: {"rows": [{"id": "PORT-TEST", "name": "Test", "country": "XX", "lat": 0.0, "lon": 0.0, "status": "open", "risk_score": 0.1}]}
UNWIND $rows AS r
MERGE (p:Port {id: r.id})
SET p:RiskBearing, p.name = r.name, p.country = r.country, p.lat = r.lat, p.lon = r.lon, p.status = r.status,
    p.risk_score = r.risk_score
