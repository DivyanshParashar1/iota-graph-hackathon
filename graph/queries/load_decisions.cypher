// name: load_decisions
// purpose: Ingest. Upsert decisions.
// kind: write
// params: {"rows": [{"id": "DEC-TEST", "summary": "Test", "decided_at": "2024-01-01", "status": "active"}]}
UNWIND $rows AS r
MERGE (d:Decision {id: r.id})
SET d.summary = r.summary, d.decided_at = r.decided_at, d.status = r.status
