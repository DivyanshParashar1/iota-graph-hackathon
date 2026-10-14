// name: blast_paths_carrier
// purpose: Highlight subgraph for a carrier strike: affected lanes with ports, top orders and customers.
// kind: read
// params: {"did": "DIS-example", "limit": 25}
MATCH (d:Disruption {id: $did})-[:AFFECTS]->(lane:Lane)<-[:SHIPS_VIA]-(o:Order {open: true})
WITH d, lane, o ORDER BY o.total DESC LIMIT $limit
MATCH (o)-[:PLACED_BY]->(c:Customer)
MATCH (lane)-[:ORIGIN]->(a:Port)
MATCH (lane)-[:DEST]->(b:Port)
RETURN d.id AS d, lane.id AS lane, a.id AS origin, b.id AS dest, o.id AS o, c.id AS c
