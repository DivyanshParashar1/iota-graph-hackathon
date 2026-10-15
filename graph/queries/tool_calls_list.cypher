// name: tool_calls_list
// purpose: Recent tool calls (newest first)
// graph: ops
// kind: read
// params: {"limit": 50}
MATCH (c:_ToolCall)
RETURN c.id AS id, c.tool AS tool, c.agent AS agent, c.args_json AS args_json, c.ms AS ms, c.ts AS ts,
       c.n AS n, c.summary AS summary
ORDER BY c.ts DESC
LIMIT $limit
