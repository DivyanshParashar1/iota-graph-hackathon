// name: conversations_all
// purpose: Memory inspector: every user's conversation counts.
// graph: mem
// kind: read
// params: {}
MATCH (u:User)-[:HAD]->(c:Conversation)
OPTIONAL MATCH (c)-[:HAS_MSG]->(m:ConvMessage)
RETURN u.id AS user_id, c.id AS id, c.started_at AS started_at, count(m) AS messages
ORDER BY started_at DESC
