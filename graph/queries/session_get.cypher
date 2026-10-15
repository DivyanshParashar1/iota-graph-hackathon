// name: session_get
// purpose: The most recent onboarding session
// graph: ops
// kind: read
// params: {}
MATCH (s:_Session)
RETURN s.id AS id, s.stage AS stage, s.started_at AS started_at, s.updated_at AS updated_at,
       s.provider AS provider, s.model AS model, s.pending_json AS pending_json
ORDER BY s.started_at DESC
LIMIT 1
