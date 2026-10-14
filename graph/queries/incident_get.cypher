// name: incident_get
// purpose: Read an incident with its disruption and affected entities.
// kind: read
// params: {"iid": "INC-example"}
MATCH (i:Incident {id: $iid})
OPTIONAL MATCH (d:Disruption)-[:TRIGGERED]->(i)
OPTIONAL MATCH (d)-[:AFFECTS]->(t)
RETURN i {.*} AS incident, d {.*} AS disruption,
       collect(DISTINCT {id: t.id, label: labels(t)[0], name: coalesce(t.name, t.id), country: t.country}) AS targets
