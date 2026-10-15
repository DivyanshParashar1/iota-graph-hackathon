// name: expert_delete
// purpose: Delete an expert role and its edges
// graph: ops
// kind: write
// params: {"id": "EXP-1"}
MATCH (e:_ExpertRole {id: $id})
DETACH DELETE e
RETURN $id AS id
