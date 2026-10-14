// name: incident_handoffs
// purpose: Handoffs recorded for an incident, in order.
// kind: read
// params: {"iid": "INC-example"}
MATCH (a:Agent)-[h:HANDED_OFF_TO {incident_id: $iid}]->(b:Agent)
RETURN a.name AS src, b.name AS dst, h.ts AS ts, h.summary AS summary
ORDER BY h.ts
