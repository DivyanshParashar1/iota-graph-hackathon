// name: tenant_upsert
// purpose: Create or update the tenant node that owns this graph
// graph: ops
// kind: write
// params: {"row": {"id": "acme_1a2b3c", "name": "Acme", "created_at": 0, "stage": "interview", "status": "onboarding"}}
MERGE (t:_Tenant {id: $row.id})
SET t += $row
RETURN t.id AS id, t.name AS name, t.stage AS stage, t.status AS status
