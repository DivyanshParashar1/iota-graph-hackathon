// name: session_set
// purpose: Patch session fields (stage, updated_at, pending_json)
// graph: ops
// kind: write
// params: {"sid": "SES-1", "patch": {"stage": "data"}}
MATCH (s:_Session {id: $sid})
SET s += $patch
RETURN s.id AS id, s.stage AS stage
