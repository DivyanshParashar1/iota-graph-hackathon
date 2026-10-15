// name: step_append
// purpose: Record one agent step (the audit and stream trail)
// graph: ops
// kind: write
// params: {"row": {"id": "STP-1", "stage": "interview", "agent": "interviewer", "kind": "llm", "summary": "", "payload_json": "{}", "ms": 0.0, "ts": 0}}
MERGE (s:_AgentStep {id: $row.id})
SET s += $row
RETURN s.id AS id
