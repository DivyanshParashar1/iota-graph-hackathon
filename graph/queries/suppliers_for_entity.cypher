// name: suppliers_for_entity
// purpose: Suppliers behind a part (active SUPPLIES) or a port (SHIPS_FROM), for ownership questions.
// kind: read
// params: {"eid": "PRT-0075"}
OPTIONAL MATCH (s1:Supplier)-[:SUPPLIES]->(:Part {id: $eid})
OPTIONAL MATCH (s2:Supplier {tier: 1})-[:SHIPS_FROM]->(:Port {id: $eid})
WITH collect(DISTINCT s1) + collect(DISTINCT s2) AS ss
UNWIND ss AS s
RETURN DISTINCT s.id AS id, s.name AS name LIMIT 5
