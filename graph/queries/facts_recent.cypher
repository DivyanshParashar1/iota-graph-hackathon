// name: facts_recent
// purpose: Memory inspector: most recent facts.
// graph: mem
// kind: read
// params: {"limit": 100}
MATCH (f:Fact)
OPTIONAL MATCH (f)-[:SUPERSEDES]->(old:Fact)
RETURN f.id AS id, f.subject_id AS subject_id, f.predicate AS predicate, f.object AS object, f.valid_at AS valid_at,
       f.invalid_at AS invalid_at, f.source AS source, f.confidence AS confidence, old.id AS supersedes
ORDER BY f.valid_at DESC LIMIT $limit
