// name: incident_option_upsert
// purpose: Create or update one proposed option of an incident, with Jev's probability and the policy verdict
// graph: ops
// kind: write
// params: {"iid": "INC-1", "row": {"id": "INC-1:G1_a", "incident_id": "INC-1", "option_id": "G1_a", "group_id": "G1", "mode": "exclusive", "title": "Reblend", "probability": 0.4, "rank": 1, "status": "pending", "reason": "", "data_json": "{}", "ts": 0}}
MATCH (i:_Incident {id: $iid})
MERGE (o:_Option {id: $row.id})
SET o += $row
MERGE (i)-[:HAS_OPTION]->(o)
RETURN o.id AS id
