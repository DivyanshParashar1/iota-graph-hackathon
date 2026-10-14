// name: load_ownership
// purpose: Ingest. Employee-[:OWNS_RELATIONSHIP {valid_from, valid_to}]->Supplier (valid_to null = current).
// kind: write
// params: {"rows": [{"employee_id": "EMP-TEST", "supplier_id": "SUP-TEST", "valid_from": "2024-01-01", "valid_to": null}]}
UNWIND $rows AS r
MATCH (e:Employee {id: r.employee_id})
MATCH (s:Supplier {id: r.supplier_id})
MERGE (e)-[o:OWNS_RELATIONSHIP {valid_from: r.valid_from}]->(s)
SET o.valid_to = r.valid_to
