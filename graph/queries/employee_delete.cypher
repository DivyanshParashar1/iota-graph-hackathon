// name: employee_delete
// purpose: Delete an employee with their chat threads and messages
// graph: ops
// kind: write
// params: {"id": "EMP-1"}
MATCH (e:_Employee {id: $id})
OPTIONAL MATCH (e)-[:HAS_THREAD]->(t:_ChatThread)
OPTIONAL MATCH (t)-[:HAS_CHAT_MESSAGE]->(m:_ChatMessage)
DETACH DELETE m, t, e
RETURN $id AS id
