// name: chat_messages_list
// purpose: Every message of one chat thread in order
// graph: ops
// kind: read
// params: {"tid": "THR-1"}
MATCH (:_ChatThread {id: $tid})-[:HAS_CHAT_MESSAGE]->(m:_ChatMessage)
RETURN m.id AS id, m.role AS role, m.text AS text, m.payload_json AS payload_json, m.seq AS seq, m.ts AS ts
ORDER BY m.seq
