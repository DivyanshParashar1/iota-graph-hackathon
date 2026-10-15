// name: expert_focus_link
// purpose: Link an expert role to the ontology types it reasons over
// graph: ops
// kind: write
// params: {"eid": "EXP-1", "labels": ["Supplier"]}
MATCH (e:_ExpertRole {id: $eid})
MATCH (ty:_OntologyType)
WHERE ty.label IN $labels
MERGE (e)-[:FOCUSES_ON]->(ty)
RETURN count(ty) AS linked
