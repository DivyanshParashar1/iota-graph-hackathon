// name: ontology_types_upsert
// purpose: One _OntologyType node per label of a spec, so experts can FOCUSES_ON them
// graph: ops
// kind: write
// params: {"oid": "ONT-1", "rows": [{"id": "OTY-ONT-1-Supplier", "label": "Supplier", "description": "", "kind": "node"}]}
MATCH (o:_OntologySpec {id: $oid})
UNWIND $rows AS r
MERGE (ty:_OntologyType {id: r.id})
SET ty += r
MERGE (o)-[:DEFINES]->(ty)
RETURN count(ty) AS types
