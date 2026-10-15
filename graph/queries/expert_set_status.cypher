// name: expert_set_status
// purpose: Approve / retire / redraft one expert role
// graph: ops
// kind: write
// params: {"id": "EXP-1", "status": "approved"}
MATCH (e:_ExpertRole {id: $id})
SET e.status = $status, e.stale = false
RETURN e.id AS id, e.status AS status
