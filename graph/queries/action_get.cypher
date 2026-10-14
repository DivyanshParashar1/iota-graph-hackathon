// name: action_get
// purpose: Q9. An action with its evidence, proposing agent and approver (explainability panel).
// kind: read
// params: {"aid": "ACT-example"}
MATCH (a:Action {id: $aid})
OPTIONAL MATCH (a)-[b:BASED_ON]->(ev)
OPTIONAL MATCH (ag:Agent)-[:PROPOSED]->(a)
OPTIONAL MATCH (a)-[:APPROVED_BY]->(u:User)
OPTIONAL MATCH (a)-[:FOR_INCIDENT]->(i:Incident)
RETURN a {.*} AS action, ag.name AS agent, u.id AS approved_by, i.id AS incident_id,
       collect(DISTINCT {label: labels(ev)[0], id: ev.id, name: coalesce(ev.name, ev.title, ev.id), role: b.role}) AS evidence
