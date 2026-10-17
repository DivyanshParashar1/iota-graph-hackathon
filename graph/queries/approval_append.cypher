// name: approval_append
// purpose: Record an approval or rejection of an option, by a person or by the auto-approval policy
// graph: ops
// kind: write
// params: {"iid": "INC-1", "row": {"id": "APR-1", "incident_id": "INC-1", "option_key": "INC-1:G1_a", "option_id": "G1_a", "actor": "user", "action": "approve", "note": "", "ts": 0, "ns": 0}}
MATCH (i:_Incident {id: $iid})
MERGE (a:_Approval {id: $row.id})
SET a += $row
MERGE (i)-[:HAS_APPROVAL]->(a)
RETURN a.id AS id
