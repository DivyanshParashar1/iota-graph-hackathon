// name: team_backups
// purpose: Backups for an owner: other members of the owner's team, past owners of the supplier first.
// kind: read
// params: {"team_id": "TEAM-PROC", "eid": "EMP-001", "sid": "SUP-T1-0001"}
MATCH (t:Team {id: $team_id})<-[:MEMBER_OF]-(m:Employee)
WHERE m.id <> $eid
OPTIONAL MATCH (m)-[past:OWNS_RELATIONSHIP]->(:Supplier {id: $sid})
RETURN m.id AS employee_id, m.name AS name, m.role AS role, count(past) AS past_windows
ORDER BY past_windows DESC, m.id LIMIT 3
