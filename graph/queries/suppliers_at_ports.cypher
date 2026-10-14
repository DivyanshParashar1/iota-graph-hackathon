// name: suppliers_at_ports
// purpose: Suppliers that ship from the given ports.
// kind: read
// params: {"ports": ["PORT-CNSHA"], "limit": 10}
UNWIND $ports AS pid
MATCH (s:Supplier)-[:SHIPS_FROM]->(p:Port {id: pid})
RETURN s.id AS id, s.name AS name, s.tier AS tier, p.id AS port
ORDER BY s.tier, s.capacity DESC LIMIT $limit
