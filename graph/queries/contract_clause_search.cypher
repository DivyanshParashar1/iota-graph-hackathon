// name: contract_clause_search
// purpose: Vector search scoped to one contract's chunks (vec.cosineDistance; lower = closer).
// kind: read
// params: {"doc_id": "DOC-CON-0001", "qvec": "$embed:delay penalty", "k": 2}
MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(ch:Chunk)
RETURN ch.id AS chunk_id, ch.text AS text, vec.cosineDistance(ch.embedding, vecf32($qvec)) AS distance
ORDER BY distance ASC LIMIT $k
