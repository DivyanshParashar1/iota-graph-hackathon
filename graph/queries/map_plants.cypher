// name: map_plants
// purpose: Map layer: plants with their export port.
// kind: read
// params: {}
MATCH (pl:Plant)-[:NEAR]->(p:Port)
RETURN pl.id AS id, pl.name AS name, pl.country AS country, pl.lat AS lat, pl.lon AS lon, p.id AS port
