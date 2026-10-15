// name: handover_open
// purpose: Delta ingest: open a new OWNS_RELATIONSHIP window (valid_from = today) for the new owner.
// kind: write
// params: {"sid": "SUP-NONE", "eid": "EMP-NONE", "today": "2026-10-15", "source": "MSG-NONE"}
MATCH (e:Employee {id: $eid})
MATCH (s:Supplier {id: $sid})
MERGE (e)-[r:OWNS_RELATIONSHIP {valid_from: $today}]->(s)
SET r.valid_to = NULL, r.source = $source
RETURN e.id AS employee_id
