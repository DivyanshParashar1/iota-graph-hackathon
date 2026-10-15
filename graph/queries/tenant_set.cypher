// name: tenant_set
// purpose: Patch tenant fields (stage, status, has_synthetic, name)
// graph: ops
// kind: write
// params: {"patch": {"stage": "data"}}
MATCH (t:_Tenant)
SET t += $patch
RETURN t.id AS id, t.stage AS stage, t.status AS status
