// name: load_chunks
// purpose: Ingest. Upsert chunks with embeddings, Document-[:HAS_CHUNK]->Chunk.
// kind: write
// params: {"rows": [{"id": "DOC-TEST#0", "doc_id": "DOC-TEST", "text": "test", "ordinal": 0, "embedding": [0.1, 0.2]}]}
UNWIND $rows AS r
MATCH (d:Document {id: r.doc_id})
MERGE (c:Chunk {id: r.id})
SET c.text = r.text, c.ordinal = r.ordinal, c.embedding = vecf32(r.embedding)
MERGE (d)-[:HAS_CHUNK]->(c)
