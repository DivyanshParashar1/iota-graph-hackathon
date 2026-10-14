// name: facts_about
// purpose: Memory (semantic): facts about a subject, current only or with history (validity windows).
// graph: mem
// kind: read
// params: {"s": "SUP-T1-0001", "history": true}
MATCH (f:Fact {subject_id: $s})
WHERE $history OR f.invalid_at IS NULL
OPTIONAL MATCH (f)-[:SUPERSEDES]->(old:Fact)
RETURN f.id AS id, f.subject_id AS subject_id, f.predicate AS predicate, f.object AS object, f.valid_at AS valid_at,
       f.invalid_at AS invalid_at, f.source AS source, f.confidence AS confidence, old.id AS supersedes
ORDER BY f.valid_at DESC
