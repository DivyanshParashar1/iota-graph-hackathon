// name: load_employees
// purpose: Ingest. Upsert synthetic employees, Employee-[:MEMBER_OF]->Team.
// kind: write
// params: {"rows": [{"id": "EMP-TEST", "name": "Test [SYNTH]", "role": "Tester", "contact": "t@ripple-demo.example", "team_id": "TEAM-TEST"}]}
UNWIND $rows AS r
MERGE (e:Employee {id: r.id})
SET e.name = r.name, e.role = r.role, e.contact = r.contact
WITH e, r
MATCH (t:Team {id: r.team_id})
MERGE (e)-[:MEMBER_OF]->(t)
