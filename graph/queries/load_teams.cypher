// name: load_teams
// purpose: Ingest. Upsert teams.
// kind: write
// params: {"rows": [{"id": "TEAM-TEST", "name": "Test"}]}
UNWIND $rows AS r
MERGE (t:Team {id: r.id})
SET t.name = r.name
