// name: load_documents
// purpose: Ingest. Upsert documents (contracts, SOPs, postmortems, chat threads).
// kind: write
// params: {"rows": [{"id": "DOC-TEST", "type": "sop", "title": "Test", "uri": "data/x.md", "version": 1, "updated_at": "2024-01-01"}]}
UNWIND $rows AS r
MERGE (d:Document {id: r.id})
SET d.type = r.type, d.title = r.title, d.uri = r.uri, d.version = r.version, d.updated_at = r.updated_at
