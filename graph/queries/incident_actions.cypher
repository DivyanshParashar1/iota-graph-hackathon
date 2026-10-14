// name: incident_actions
// purpose: Actions of an incident with status (for episodes and the incident view).
// kind: read
// params: {"iid": "INC-example"}
MATCH (a:Action)-[:FOR_INCIDENT]->(i:Incident {id: $iid})
OPTIONAL MATCH (ag:Agent)-[:PROPOSED]->(a)
RETURN a.id AS id, a.type AS type, a.status AS status, a.summary AS summary, a.created_at AS created_at,
       a.executed_at AS executed_at, ag.name AS agent
ORDER BY a.created_at
