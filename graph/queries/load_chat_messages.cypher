// name: load_chat_messages
// purpose: Ingest. Upsert chat messages with embeddings; Thread-[:HAS_MSG]->ChatMessage, Employee-[:POSTED]->ChatMessage.
// kind: write
// params: {"rows": [{"id": "MSG-TEST", "thread_id": "THR-TEST", "author": "EMP-TEST", "ts": "2024-01-01T09:00", "text": "hi", "embedding": [0.1, 0.2]}]}
UNWIND $rows AS r
MATCH (t:Thread {id: r.thread_id})
MERGE (m:ChatMessage {id: r.id})
SET m.ts = r.ts, m.text = r.text, m.embedding = vecf32(r.embedding)
MERGE (t)-[:HAS_MSG]->(m)
WITH m, r
MATCH (e:Employee {id: r.author})
MERGE (e)-[:POSTED]->(m)
