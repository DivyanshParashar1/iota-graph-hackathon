// name: formspec_set_status
// purpose: Mark a form round open or submitted
// graph: ops
// kind: write
// params: {"id": "FRM-1", "status": "submitted"}
MATCH (f:_FormSpec {id: $id})
SET f.status = $status
RETURN f.id AS id, f.status AS status
