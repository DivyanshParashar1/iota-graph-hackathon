// name: incident_option_set
// purpose: Patch one option (its status after an approval, a rejection or a superseding choice)
// graph: ops
// kind: write
// params: {"id": "INC-1:G1_a", "patch": {"status": "approved"}}
MATCH (o:_Option {id: $id})
SET o += $patch
RETURN o.id AS id, o.status AS status
