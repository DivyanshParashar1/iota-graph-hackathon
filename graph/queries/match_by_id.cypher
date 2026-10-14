// name: match_by_id
// purpose: Event matching: a RiskBearing node by id.
// kind: read
// params: {"id": "PORT-CNSHA"}
MATCH (n:RiskBearing {id: $id})
RETURN n.id AS id, labels(n)[0] AS label, coalesce(n.name, n.id) AS name, n.country AS country, n.lat AS lat, n.lon AS lon
