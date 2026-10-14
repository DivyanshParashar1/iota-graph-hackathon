// name: match_lanes_by_carrier
// purpose: Event matching: every lane operated by a carrier (carrier strike).
// kind: read
// params: {"name": "Pacific Arc Shipping"}
MATCH (l:Lane)-[:ORIGIN]->(o:Port)
WHERE toLower(l.carrier) = toLower($name)
RETURN l.id AS id, 'Lane' AS label, l.id AS name, o.country AS country, o.lat AS lat, o.lon AS lon, l.carrier AS carrier
