// name: message_append
// purpose: Append one chat message to a session
// graph: ops
// kind: write
// params: {"sid": "SES-1", "row": {"id": "MSG-1", "role": "user", "agent": "", "stage": "interview", "kind": "text", "text": "hi", "payload_json": "{}", "ts": 0, "seq": 1}}
MATCH (s:_Session {id: $sid})
MERGE (m:_Message {id: $row.id})
SET m += $row
MERGE (s)-[:HAS_MESSAGE]->(m)
RETURN m.id AS id, m.seq AS seq
