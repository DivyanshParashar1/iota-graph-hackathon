// name: ontology_upsert
// purpose: Store a new version of the generated ontology spec
// graph: ops
// kind: write
// params: {"row": {"id": "ONT-1", "version": 1, "json": "{}", "status": "draft", "rationale": "", "stale": false, "ts": 0}}
MERGE (o:_OntologySpec {id: $row.id})
SET o += $row
RETURN o.id AS id, o.version AS version, o.status AS status
