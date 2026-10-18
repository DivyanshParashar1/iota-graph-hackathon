// name: chat_threads_list
// purpose: One employee's chat threads, most recently active first
// graph: ops
// kind: read
// params: {"eid": "EMP-1", "limit": 30}
MATCH (:_Employee {id: $eid})-[:HAS_THREAD]->(t:_ChatThread)
RETURN t.id AS id, t.title AS title, t.ts AS ts, t.updated_at AS updated_at
ORDER BY t.updated_at DESC
LIMIT $limit
