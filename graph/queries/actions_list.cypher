// name: actions_list
// purpose: Action queue: actions filtered by status and/or incident, newest first.
// kind: read
// params: {"status": "proposed", "iid": null, "limit": 100}
MATCH (a:Action)
WHERE ($status IS NULL OR a.status = $status) AND ($iid IS NULL OR a.incident_id = $iid)
OPTIONAL MATCH (ag:Agent)-[:PROPOSED]->(a)
RETURN a {.*} AS action, ag.name AS agent
ORDER BY a.created_at DESC LIMIT $limit
