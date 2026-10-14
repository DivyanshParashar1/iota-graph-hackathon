// name: fact_create
// purpose: Memory (semantic): create a fact; if it contradicts the current one, close the old window (invalid_at) and link Fact-[:SUPERSEDES]->Fact.
// graph: mem
// kind: write
// params: {"id": "FACT-test", "s": "SUP-T1-0001", "p": "reliability", "o": "high", "ts": 0, "source": "test", "confidence": 1.0, "old": null}
MERGE (f:Fact {id: $id})
ON CREATE SET f.subject_id = $s, f.predicate = $p, f.object = $o, f.valid_at = $ts, f.source = $source,
              f.confidence = $confidence
WITH f
OPTIONAL MATCH (old:Fact {id: $old})
FOREACH (_ IN CASE WHEN old IS NULL THEN [] ELSE [1] END |
  SET old.invalid_at = $ts
  MERGE (f)-[:SUPERSEDES]->(old))
RETURN f.id AS id
