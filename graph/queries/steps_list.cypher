// name: steps_list
// purpose: Agent steps in order, newest last (optionally one stage)
// graph: ops
// kind: read
// params: {"stage": "", "limit": 200}
MATCH (s:_AgentStep)
WHERE $stage = '' OR s.stage = $stage
RETURN s.id AS id, s.stage AS stage, s.agent AS agent, s.kind AS kind, s.summary AS summary,
       s.payload_json AS payload_json, s.ms AS ms, s.ts AS ts
ORDER BY s.ts
LIMIT $limit
