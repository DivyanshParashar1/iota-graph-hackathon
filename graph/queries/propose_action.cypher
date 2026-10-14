// name: propose_action
// purpose: Write: MERGE a proposed Action (deterministic id) for an incident; Agent-[:PROPOSED]->Action-[:FOR_INCIDENT]->Incident.
// kind: write
// params: {"iid": "INC-example", "aid": "ACT-example", "type": "NOTIFY_OWNER", "params": "{}", "ts": 0, "impact": 0.0, "summary": "", "agent": "planner"}
MATCH (i:Incident {id: $iid})
MERGE (a:Action {id: $aid})
ON CREATE SET a.type = $type, a.status = 'proposed', a.params_json = $params, a.created_at = $ts,
              a.expected_impact = $impact, a.summary = $summary, a.incident_id = $iid
MERGE (a)-[:FOR_INCIDENT]->(i)
MERGE (ag:Agent {name: $agent})
ON CREATE SET ag.id = 'AGT-' + $agent
MERGE (ag)-[p:PROPOSED]->(a)
ON CREATE SET p.ts = $ts
RETURN a.id AS id, a.status AS status, a.type AS type, a.created_at = $ts AS created
