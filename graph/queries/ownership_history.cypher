// name: ownership_history
// purpose: Every ownership window for a supplier, newest first.
// kind: read
// params: {"sid": "SUP-T1-0001"}
MATCH (e:Employee)-[r:OWNS_RELATIONSHIP]->(s:Supplier {id: $sid})
RETURN e.id AS employee_id, e.name AS name, r.valid_from AS valid_from, r.valid_to AS valid_to
ORDER BY r.valid_from DESC
