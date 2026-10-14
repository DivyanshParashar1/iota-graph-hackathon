// name: finish_execution
// purpose: Write: mark an action executed with its before-state (undo_json); Agent-[:EXECUTED]->Action.
// kind: write
// params: {"aid": "ACT-example", "ts": 0, "undo": "{}", "result": "{}", "agent": "planner", "status": "executed"}
MATCH (a:Action {id: $aid})
SET a.status = $status, a.executed_at = $ts, a.undo_json = $undo, a.result_json = $result
MERGE (ag:Agent {name: $agent})
ON CREATE SET ag.id = 'AGT-' + $agent
MERGE (ag)-[e:EXECUTED]->(a)
SET e.ts = $ts
RETURN a.id AS id, a.status AS status
