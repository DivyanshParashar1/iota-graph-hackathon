// name: log_tool_call
// purpose: Write: one ToolCall node per tool invocation, linked from the incident when there is one.
// kind: write
// params: {"id": "TC-example", "tool": "blast_radius", "agent": "analyst", "args": "{}", "ms": 1.0, "ts": 0, "n": 0, "iid": "INC-example"}
CREATE (t:ToolCall {id: $id, tool: $tool, agent: $agent, args_json: $args, ms: $ms, ts: $ts, n_nodes: $n})
WITH t
OPTIONAL MATCH (i:Incident {id: $iid})
FOREACH (_ IN CASE WHEN i IS NULL THEN [] ELSE [1] END | MERGE (i)-[:HAS_CALL]->(t))
RETURN t.id AS id
