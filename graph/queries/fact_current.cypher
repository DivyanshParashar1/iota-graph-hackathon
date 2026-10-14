// name: fact_current
// purpose: Memory (semantic): the current (invalid_at IS NULL) fact for a subject and predicate.
// graph: mem
// kind: read
// params: {"s": "SUP-T1-0001", "p": "reliability"}
MATCH (f:Fact {subject_id: $s})
WHERE f.predicate = $p AND f.invalid_at IS NULL
RETURN f.id AS id, f.object AS object, f.valid_at AS valid_at
