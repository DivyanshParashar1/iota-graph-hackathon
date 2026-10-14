// name: load_contract_docs
// purpose: Ingest. Contract-[:DOCUMENTED_IN]->Document.
// kind: write
// params: {"rows": [{"contract_id": "CON-TEST", "doc_id": "DOC-TEST"}]}
UNWIND $rows AS r
MATCH (k:Contract {id: r.contract_id})
MATCH (d:Document {id: r.doc_id})
MERGE (k)-[:DOCUMENTED_IN]->(d)
