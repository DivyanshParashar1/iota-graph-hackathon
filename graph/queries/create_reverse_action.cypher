// name: create_reverse_action
// purpose: Write: the reverse Action created by undo; ReverseAction-[:REVERSES]->Action, original status 'undone'.
// kind: write
// params: {"aid": "ACT-example", "rid": "ACT-example-U", "ts": 0, "agent": "api"}
MATCH (a:Action {id: $aid})
MERGE (r:Action {id: $rid})
ON CREATE SET r.type = 'UNDO_' + a.type, r.status = 'executed', r.created_at = $ts, r.executed_at = $ts,
              r.params_json = a.undo_json, r.incident_id = a.incident_id, r.summary = 'Undo of ' + a.id
MERGE (r)-[:REVERSES]->(a)
WITH a, r
OPTIONAL MATCH (a)-[:FOR_INCIDENT]->(i:Incident)
FOREACH (_ IN CASE WHEN i IS NULL THEN [] ELSE [1] END | MERGE (r)-[:FOR_INCIDENT]->(i))
SET a.status = 'undone', a.undone_at = $ts
RETURN r.id AS id
