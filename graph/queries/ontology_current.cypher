// name: ontology_current
// purpose: The latest ontology spec of any status
// graph: ops
// kind: read
// params: {}
MATCH (o:_OntologySpec)
RETURN o.id AS id, o.version AS version, o.json AS json, o.status AS status, o.rationale AS rationale,
       o.stale AS stale, o.ts AS ts
ORDER BY o.version DESC
LIMIT 1
