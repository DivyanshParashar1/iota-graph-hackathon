// name: owners_for_entities
// purpose: Current relationship owners (Q6 pattern) for a list of suppliers.
// kind: read
// params: {"ids": ["SUP-T1-0001"], "now": "2026-10-15"}
UNWIND $ids AS sid
MATCH (e:Employee)-[r:OWNS_RELATIONSHIP]->(s:Supplier {id: sid})
WHERE r.valid_from <= $now AND (r.valid_to IS NULL OR r.valid_to > $now)
OPTIONAL MATCH (e)-[:MEMBER_OF]->(t:Team)
RETURN s.id AS supplier_id, s.name AS supplier, e.id AS employee_id, e.name AS name, e.role AS role, t.name AS team
