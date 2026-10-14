// name: close_incident
// purpose: Write: close the incident, deactivate its disruption and reset the status of what it affected.
// kind: write
// params: {"iid": "INC-example", "ts": 0, "outcome": "resolved", "episode_id": "EPI-example"}
MATCH (i:Incident {id: $iid})
SET i.status = 'closed', i.closed_at = $ts, i.outcome = $outcome, i.episode_id = $episode_id
WITH i
OPTIONAL MATCH (d:Disruption)-[:TRIGGERED]->(i)
SET d.active = false
WITH i, d
OPTIONAL MATCH (d)-[:AFFECTS]->(t)
SET t.status = CASE WHEN t:Supplier THEN 'active' ELSE 'open' END
RETURN i.id AS id, i.status AS status
