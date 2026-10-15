// name: ontology_approved
// purpose: The approved ontology spec the instance data is loaded against
// graph: ops
// kind: read
// params: {}
MATCH (o:_OntologySpec {status: 'approved'})
RETURN o.id AS id, o.version AS version, o.json AS json, o.rationale AS rationale, o.stale AS stale, o.ts AS ts
ORDER BY o.version DESC
LIMIT 1
