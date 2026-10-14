// name: who_owns
// purpose: Q6. Who owns the supplier relationship at a point in time (temporal OWNS_RELATIONSHIP window) and their team.
// kind: read
// params: {"sid": "SUP-T1-0001", "now": "2026-10-15"}
MATCH (e:Employee)-[r:OWNS_RELATIONSHIP]->(s:Supplier {id: $sid})
WHERE r.valid_from <= $now AND (r.valid_to IS NULL OR r.valid_to > $now)
OPTIONAL MATCH (e)-[:MEMBER_OF]->(t:Team)
RETURN s.id AS supplier_id, s.name AS supplier, e.id AS employee_id, e.name AS name, e.role AS role,
       t.id AS team_id, t.name AS team, r.valid_from AS valid_from, r.valid_to AS valid_to
