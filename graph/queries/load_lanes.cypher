// name: load_lanes
// purpose: Ingest. Upsert lanes (RiskBearing) with ORIGIN and DEST ports.
// kind: write
// params: {"rows": [{"id": "LANE-TEST", "origin": "PORT-TEST", "dest": "PORT-TEST", "mode": "Standard Class", "transit_days": 1.0, "carrier": "Test", "risk_score": 0.1}]}
UNWIND $rows AS r
MERGE (l:Lane {id: r.id})
SET l:RiskBearing, l.mode = r.mode, l.transit_days = r.transit_days, l.carrier = r.carrier, l.risk_score = r.risk_score
WITH l, r
MATCH (o:Port {id: r.origin})
MATCH (d:Port {id: r.dest})
MERGE (l)-[:ORIGIN]->(o)
MERGE (l)-[:DEST]->(d)
