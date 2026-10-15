// name: session_upsert
// purpose: Create or update the onboarding session (stage cursor, provider, model)
// graph: ops
// kind: write
// params: {"row": {"id": "SES-1", "stage": "interview", "started_at": 0, "updated_at": 0, "provider": "claude_code", "model": "opus"}}
MERGE (s:_Session {id: $row.id})
SET s += $row
WITH s
MATCH (t:_Tenant)
MERGE (t)-[:HAS_SESSION]->(s)
RETURN s.id AS id, s.stage AS stage
