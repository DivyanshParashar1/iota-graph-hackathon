// name: steps_count
// purpose: How many agent steps there are (optionally one stage)
// graph: ops
// kind: read
// params: {"stage": ""}
MATCH (s:_AgentStep)
WHERE $stage = '' OR s.stage = $stage
RETURN count(s) AS n
