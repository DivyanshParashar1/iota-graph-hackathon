// name: artifacts_mark_stale
// purpose: Flag every artifact of these labels stale (downstream of a changed upstream artifact)
// graph: ops
// kind: write
// params: {"labels": ["_OntologySpec"]}
MATCH (n)
WHERE any(l IN labels(n) WHERE l IN $labels)
SET n.stale = true
RETURN count(n) AS flagged
