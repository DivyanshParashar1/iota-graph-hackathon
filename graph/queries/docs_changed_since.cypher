// name: docs_changed_since
// purpose: Documents revised (version > 1) since a date: what changed in policy.
// kind: read
// params: {"since": "2024-01-01"}
MATCH (d:Document)
WHERE d.version > 1 AND d.updated_at >= $since
OPTIONAL MATCH (d)-[:HAS_CHUNK]->(ch:Chunk)
WITH d, ch ORDER BY ch.ordinal
RETURN d.id AS doc_id, d.title AS title, d.uri AS uri, d.version AS version, d.updated_at AS updated_at,
       collect(ch.text)[0..2] AS texts, collect(ch.id)[0..2] AS chunk_ids
ORDER BY updated_at DESC
