// name: jev_decision_append
// purpose: Record one Jev call of an incident: why it was asked, the request, the answers and the build
// graph: ops
// kind: write
// params: {"iid": "INC-1", "row": {"id": "JEV-1", "incident_id": "INC-1", "purpose": "decision", "request_json": "{}", "result_json": "{}", "model": "typesafe/jev-1.13", "ms": 0.0, "ts": 0, "ns": 0}}
MATCH (i:_Incident {id: $iid})
MERGE (d:_JevDecision {id: $row.id})
SET d += $row
MERGE (i)-[:DECIDED_BY]->(d)
RETURN d.id AS id
