// name: ontology_types_list
// purpose: The declared types of one spec
// graph: ops
// kind: read
// params: {"oid": "ONT-1"}
MATCH (:_OntologySpec {id: $oid})-[:DEFINES]->(ty:_OntologyType)
RETURN ty.id AS id, ty.label AS label, ty.description AS description, ty.kind AS kind
ORDER BY ty.kind, ty.label
