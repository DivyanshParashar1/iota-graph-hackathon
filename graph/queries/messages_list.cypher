// name: messages_list
// purpose: Every message of a session in order, optionally after a sequence number
// graph: ops
// kind: read
// params: {"sid": "SES-1", "after": 0}
MATCH (:_Session {id: $sid})-[:HAS_MESSAGE]->(m:_Message)
WHERE m.seq > $after
RETURN m.id AS id, m.role AS role, m.agent AS agent, m.stage AS stage, m.kind AS kind, m.text AS text,
       m.payload_json AS payload_json, m.ts AS ts, m.seq AS seq
ORDER BY m.seq
