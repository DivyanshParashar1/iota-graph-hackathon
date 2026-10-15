// name: ontology_supersede_others
// purpose: Mark every approved spec other than this one superseded
// graph: ops
// kind: write
// params: {"id": "ONT-2"}
MATCH (o:_OntologySpec {status: 'approved'})
WHERE o.id <> $id
SET o.status = 'superseded'
RETURN count(o) AS superseded
