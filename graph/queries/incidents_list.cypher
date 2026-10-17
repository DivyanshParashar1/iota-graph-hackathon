// name: incidents_list
// purpose: Incidents, newest first, without their artifacts
// graph: ops
// kind: read
// params: {"limit": 50}
MATCH (i:_Incident)
RETURN i.id AS id, i.kind AS kind, i.summary AS summary, i.source AS source, i.status AS status,
       i.priority AS priority, i.auto AS auto, i.received_at AS received_at, i.error AS error, i.ts AS ts,
       i.updated_at AS updated_at
ORDER BY i.ts DESC
LIMIT $limit
