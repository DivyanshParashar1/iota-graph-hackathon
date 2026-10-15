// name: ontology_set_status
// purpose: Approve / supersede one ontology spec version
// graph: ops
// kind: write
// params: {"id": "ONT-1", "status": "approved"}
MATCH (o:_OntologySpec {id: $id})
SET o.status = $status
RETURN o.id AS id, o.status AS status
