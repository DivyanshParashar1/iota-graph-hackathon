// name: match_port_by_name
// purpose: Event matching: ports whose name contains the event's target name.
// kind: read
// params: {"name": "Shanghai"}
MATCH (p:Port)
WHERE toLower(p.name) CONTAINS toLower($name) OR p.id = $name
RETURN p.id AS id, 'Port' AS label, p.name AS name, p.country AS country, p.lat AS lat, p.lon AS lon
