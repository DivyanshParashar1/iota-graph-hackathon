// name: load_threads
// purpose: Ingest. Upsert chat threads, Thread-[:THREAD_DOC]->Document.
// kind: write
// params: {"rows": [{"id": "THR-TEST", "channel": "#test", "title": "Test", "doc_id": "DOC-TEST"}]}
UNWIND $rows AS r
MERGE (t:Thread {id: r.id})
SET t.channel = r.channel, t.title = r.title
WITH t, r
MATCH (d:Document {id: r.doc_id})
MERGE (t)-[:THREAD_DOC]->(d)
