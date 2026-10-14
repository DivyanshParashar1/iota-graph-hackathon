// name: log_conversation_turn
// purpose: Memory (conversation): (:User)-[:HAD]->(:Conversation)-[:HAS_MSG]->(:ConvMessage).
// graph: mem
// kind: write
// params: {"uid": "USR-demo", "cid": "CONV-test", "mid": "CMSG-test", "role": "user", "text": "hi", "ts": 0, "sources": "[]"}
MERGE (u:User {id: $uid})
ON CREATE SET u.name = $uid
MERGE (c:Conversation {id: $cid})
ON CREATE SET c.user_id = $uid, c.started_at = $ts
MERGE (u)-[:HAD]->(c)
MERGE (m:ConvMessage {id: $mid})
ON CREATE SET m.role = $role, m.text = $text, m.ts = $ts, m.sources_json = $sources
MERGE (c)-[:HAS_MSG]->(m)
RETURN m.id AS id
