// name: incident_upsert
// purpose: Create or update an incident (one reported event and everything the pipeline made of it)
// graph: ops
// kind: write
// params: {"row": {"id": "INC-1", "kind": "site_incident", "summary": "Fire at the bonded warehouse", "source": "webhook", "received_at": "2026-10-17T06:42:00Z", "status": "received", "ts": 0, "updated_at": 0}}
MERGE (i:_Incident {id: $row.id})
SET i += $row
RETURN i.id AS id, i.status AS status
