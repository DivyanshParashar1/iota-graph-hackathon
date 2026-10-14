// name: blast_paths_port
// purpose: Highlight subgraph for a port closure: top orders by value with their lane, customer and products.
// kind: read
// params: {"did": "DIS-example", "limit": 25}
MATCH (d:Disruption {id: $did})-[:AFFECTS]->(port:Port)<-[r:ORIGIN|DEST]-(lane:Lane)<-[:SHIPS_VIA]-(o:Order {open: true})
WITH d, port, lane, type(r) AS rt, o
ORDER BY o.total DESC LIMIT $limit
MATCH (o)-[:PLACED_BY]->(c:Customer)
OPTIONAL MATCH (o)-[:CONTAINS]->(:OrderLine)-[:CONTAINS]->(pr:Product)
OPTIONAL MATCH (pr)-[:MADE_AT]->(pl:Plant)
RETURN d.id AS d, port.id AS port, rt, lane.id AS lane, o.id AS o, c.id AS c,
       collect(DISTINCT [pr.id, pl.id]) AS products
