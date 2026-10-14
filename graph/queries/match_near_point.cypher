// name: match_near_point
// purpose: Event matching: every port and supplier with coordinates; the haversine radius filter runs in Python.
// kind: read
// params: {}
MATCH (n:RiskBearing)
WHERE n.lat IS NOT NULL AND (n:Port OR n:Supplier)
RETURN n.id AS id, labels(n)[0] AS label, n.name AS name, n.country AS country, n.lat AS lat, n.lon AS lon
