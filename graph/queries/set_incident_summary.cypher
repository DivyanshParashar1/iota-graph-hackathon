// name: set_incident_summary
// purpose: Write: final Comms summary on the Incident blackboard.
// kind: write
// params: {"iid": "INC-example", "summary": "", "sources": []}
MATCH (i:Incident {id: $iid})
SET i.summary = $summary, i.sources = $sources
RETURN i.id AS id
