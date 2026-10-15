// name: delta_upsert_thread
// purpose: Delta ingest: MERGE the live chat thread for a channel and its citable Document.
// kind: write
// params: {"tid": "THR-D-test", "doc_id": "DOC-CHAT-D-test", "channel": "#test", "title": "Live: #test", "uri": "live://chat/test", "ts": "2026-10-15"}
MERGE (d:Document {id: $doc_id})
ON CREATE SET d.type = 'chat_thread', d.title = $title, d.uri = $uri, d.version = 1
SET d.updated_at = $ts
MERGE (t:Thread {id: $tid})
ON CREATE SET t.channel = $channel, t.title = $title
MERGE (t)-[:THREAD_DOC]->(d)
RETURN t.id AS tid, d.id AS doc_id
