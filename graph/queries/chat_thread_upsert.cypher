// name: chat_thread_upsert
// purpose: Create or update one employee's chat thread with the workspace orchestrator
// graph: ops
// kind: write
// params: {"eid": "EMP-1", "row": {"id": "THR-1", "employee_id": "EMP-1", "title": "Late shipments", "ts": 0, "updated_at": 0}}
MATCH (e:_Employee {id: $eid})
MERGE (t:_ChatThread {id: $row.id})
SET t += $row
MERGE (e)-[:HAS_THREAD]->(t)
RETURN t.id AS id
