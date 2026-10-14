// name: load_plants
// purpose: Ingest. Upsert plants, Plant-[:NEAR]->Port.
// kind: write
// params: {"rows": [{"id": "PLT-TEST", "name": "Test", "country": "XX", "lat": 0.0, "lon": 0.0, "port_id": "PORT-TEST", "port_km": 1.0}]}
UNWIND $rows AS r
MERGE (p:Plant {id: r.id})
SET p.name = r.name, p.country = r.country, p.lat = r.lat, p.lon = r.lon
WITH p, r
MATCH (po:Port {id: r.port_id})
MERGE (p)-[n:NEAR]->(po)
SET n.km = r.port_km
