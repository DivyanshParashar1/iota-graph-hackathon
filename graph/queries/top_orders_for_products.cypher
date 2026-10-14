// name: top_orders_for_products
// purpose: Highlight helper: the most valuable open orders containing the given products.
// kind: read
// params: {"products": ["PRD-1360"], "limit": 20}
UNWIND $products AS pid
MATCH (pr:Product {id: pid})<-[:CONTAINS]-(:OrderLine)<-[:CONTAINS]-(o:Order {open: true})-[:PLACED_BY]->(c:Customer)
WITH DISTINCT o, c, pr
ORDER BY o.total DESC LIMIT $limit
RETURN o.id AS o, c.id AS c, pr.id AS product
