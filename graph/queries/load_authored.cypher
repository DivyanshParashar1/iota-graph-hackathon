// name: load_authored
// purpose: Ingest. Employee-[:AUTHORED]->Document.
// kind: write
// params: {"rows": [{"employee_id": "EMP-TEST", "doc_id": "DOC-TEST"}]}
UNWIND $rows AS r
MATCH (e:Employee {id: r.employee_id})
MATCH (d:Document {id: r.doc_id})
MERGE (e)-[:AUTHORED]->(d)
