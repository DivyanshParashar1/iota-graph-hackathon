// name: load_connects
// purpose: Ingest. Port-[:CONNECTS {transit_days}]->Port materialized from lanes (sea days).
// kind: write
// params: {"rows": [{"src": "PORT-TEST", "dst": "PORT-TEST", "transit_days": 1.0}]}
UNWIND $rows AS r
MATCH (a:Port {id: r.src})
MATCH (b:Port {id: r.dst})
MERGE (a)-[c:CONNECTS]->(b)
SET c.transit_days = r.transit_days
