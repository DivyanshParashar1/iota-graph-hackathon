// name: ontology_versions
// purpose: Every ontology spec version, newest first
// graph: ops
// kind: read
// params: {}
MATCH (o:_OntologySpec)
RETURN o.id AS id, o.version AS version, o.status AS status, o.stale AS stale, o.ts AS ts
ORDER BY o.version DESC
