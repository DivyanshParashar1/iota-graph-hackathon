// name: instance_wipe
// purpose: Delete every instance node of the generated ontology (re-load after a new approved spec)
// graph: ops
// kind: write
// params: {}
MATCH (n)
WHERE NOT any(l IN labels(n) WHERE l STARTS WITH '_')
DETACH DELETE n
RETURN count(n) AS deleted
