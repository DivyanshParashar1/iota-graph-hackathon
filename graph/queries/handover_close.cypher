// name: handover_close
// purpose: Delta ingest: close the current OWNS_RELATIONSHIP window of a supplier (valid_to = today).
// kind: write
// params: {"sid": "SUP-NONE", "today": "2026-10-15"}
MATCH (e:Employee)-[r:OWNS_RELATIONSHIP]->(s:Supplier {id: $sid})
WHERE r.valid_to IS NULL
SET r.valid_to = $today
RETURN e.id AS employee_id, r.valid_from AS valid_from
