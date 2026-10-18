// name: chat_message_append
// purpose: Append one message (the employee's, or the orchestrator's answer with its delegations) to a thread
// graph: ops
// kind: write
// params: {"tid": "THR-1", "row": {"id": "CMS-1", "role": "user", "text": "hi", "payload_json": "{}", "seq": 1, "ts": 0}}
MATCH (t:_ChatThread {id: $tid})
MERGE (m:_ChatMessage {id: $row.id})
SET m += $row
MERGE (t)-[:HAS_CHAT_MESSAGE]->(m)
RETURN m.id AS id, m.seq AS seq
