// name: port_coords
// purpose: All ports with coordinates (for nearest-open-port search in alt_route).
// kind: read
// params: {}
MATCH (p:Port)
RETURN p.id AS id, p.name AS name, p.country AS country, p.lat AS lat, p.lon AS lon
