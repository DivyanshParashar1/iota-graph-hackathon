// name: tool_call_log
// purpose: Record one tool call so an expert's answer can be traced back to the queries behind it
// graph: ops
// kind: write
// params: {"row": {"id": "TC-1", "tool": "find_nodes", "agent": "sourcing_risk", "args_json": "{}", "ms": 1.0, "ts": 0, "n": 0, "summary": ""}}
MERGE (c:_ToolCall {id: $row.id})
SET c += $row
RETURN c.id AS id
