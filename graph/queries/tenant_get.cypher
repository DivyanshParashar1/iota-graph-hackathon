// name: tenant_get
// purpose: The tenant node (id, name, stage, status, flags)
// graph: ops
// kind: read
// params: {}
MATCH (t:_Tenant)
RETURN t.id AS id, t.name AS name, t.created_at AS created_at, t.stage AS stage, t.status AS status,
       t.has_synthetic AS has_synthetic, t.industry AS industry
LIMIT 1
