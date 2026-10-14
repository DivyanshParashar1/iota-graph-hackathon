// name: docs_get
// purpose: Documents by id (title, uri, first chunk) for citations.
// kind: read
// params: {"ids": ["DOC-CON-0001"]}
UNWIND $ids AS did
MATCH (d:Document {id: did})
OPTIONAL MATCH (d)-[:HAS_CHUNK]->(ch:Chunk {ordinal: 0})
RETURN d.id AS doc_id, d.title AS title, d.uri AS uri, d.type AS type, ch.id AS chunk_id, ch.text AS text
