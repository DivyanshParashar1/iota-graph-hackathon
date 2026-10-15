// name: message_max_seq
// purpose: The highest message sequence number in a session (0 when empty)
// graph: ops
// kind: read
// params: {"sid": "SES-1"}
MATCH (:_Session {id: $sid})-[:HAS_MESSAGE]->(m:_Message)
RETURN coalesce(max(m.seq), 0) AS seq
