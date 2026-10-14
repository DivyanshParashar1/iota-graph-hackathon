// name: open_incident
// purpose: Write: MERGE the Incident (shared blackboard) for a disruption, Disruption-[:TRIGGERED]->Incident.
// kind: write
// params: {"did": "DIS-example", "iid": "INC-example", "ts": 0, "mode": "scripted"}
MATCH (d:Disruption {id: $did})
MERGE (i:Incident {id: $iid})
ON CREATE SET i.status = 'open', i.opened_at = $ts, i.type = d.type, i.title = d.name, i.mode = $mode,
              i.disruption_id = d.id, i.expected_days = d.expected_days
MERGE (d)-[:TRIGGERED]->(i)
RETURN i.id AS id, i.status AS status, i.opened_at AS opened_at, i.type AS type, i.title AS title
