// name: chat_thread_delete
// purpose: Delete one chat thread and its messages
// graph: ops
// kind: write
// params: {"id": "THR-1"}
MATCH (t:_ChatThread {id: $id})
OPTIONAL MATCH (t)-[:HAS_CHAT_MESSAGE]->(m:_ChatMessage)
DETACH DELETE m, t
RETURN $id AS id
