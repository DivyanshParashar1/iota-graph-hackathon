// name: disruptions_active
// purpose: Active disruptions with what they affect (lanes collapsed to a count).
// kind: read
// params: {}
MATCH (d:Disruption {active: true})
OPTIONAL MATCH (d)-[:AFFECTS]->(t)
OPTIONAL MATCH (d)-[:TRIGGERED]->(i:Incident)
RETURN d.id AS id, d.type AS type, d.name AS name, d.severity AS severity, d.started_at AS started_at,
       d.expected_days AS expected_days, i.id AS incident_id,
       collect(DISTINCT CASE WHEN t:Lane THEN NULL ELSE t.id END) AS targets, count(DISTINCT t) AS n_targets
