// name: incident_tool_calls
// purpose: Tool calls logged for an incident (used to replay the timeline after a restart).
// kind: read
// params: {"iid": "INC-example"}
MATCH (:Incident {id: $iid})-[:HAS_CALL]->(t:ToolCall)
RETURN t.id AS id, t.tool AS tool, t.agent AS agent, t.args_json AS args_json, t.ms AS ms, t.ts AS ts,
       t.n_nodes AS n_nodes
ORDER BY t.ts
