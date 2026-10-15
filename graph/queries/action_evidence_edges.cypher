// name: action_evidence_edges
// purpose: Actions of an incident with their BASED_ON evidence (for the incident graph).
// kind: read
// params: {"iid": "INC-example"}
MATCH (a:Action)-[:FOR_INCIDENT]->(:Incident {id: $iid})
OPTIONAL MATCH (a)-[:BASED_ON]->(ev)
RETURN a.id AS action, a.type AS type, collect(ev.id)[0..12] AS evidence
