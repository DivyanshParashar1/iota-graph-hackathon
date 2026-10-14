// name: load_customers
// purpose: Ingest. Upsert customers (id, segment and city-level location only; no PII).
// kind: write
// params: {"rows": [{"id": "CUS-TEST", "segment": "Consumer", "city": "X", "state": "Y", "country": "Z"}]}
UNWIND $rows AS r
MERGE (c:Customer {id: r.id})
SET c.segment = r.segment, c.city = r.city, c.state = r.state, c.country = r.country
