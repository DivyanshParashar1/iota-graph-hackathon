// name: doc_search
// purpose: Q8. Ontology-augmented doc search: vector search over chunks, then expand to the document and the entities each chunk MENTIONS; optional entity scope filter.
// kind: read
// params: {"qvec": "$embed:battery dual source", "k": 8, "scope": []}
CALL db.idx.vector.queryNodes('Chunk', 'embedding', $k, vecf32($qvec)) YIELD node AS ch, score
MATCH (doc:Document)-[:HAS_CHUNK]->(ch)
OPTIONAL MATCH (ch)-[:MENTIONS]->(ent)
WITH doc, ch, score, collect(DISTINCT ent) AS ents
WHERE size($scope) = 0 OR any(e IN ents WHERE e.id IN $scope)
RETURN doc.id AS doc_id, doc.title AS title, doc.uri AS uri, doc.type AS type, ch.id AS chunk_id, ch.text AS text,
       score, [e IN ents | e.id] AS entity_ids, [e IN ents | e.name] AS entities
ORDER BY score ASC
