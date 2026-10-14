// name: conversations_for_user
// purpose: Memory (conversation): a user's conversations with their messages.
// graph: mem
// kind: read
// params: {"uid": "USR-demo"}
MATCH (u:User {id: $uid})-[:HAD]->(c:Conversation)-[:HAS_MSG]->(m:ConvMessage)
WITH c, m ORDER BY m.ts
RETURN c.id AS id, c.started_at AS started_at, collect({id: m.id, role: m.role, text: m.text, ts: m.ts,
       sources_json: m.sources_json}) AS messages
ORDER BY started_at DESC
