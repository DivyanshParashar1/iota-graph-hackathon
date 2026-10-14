// name: impact_expand
// purpose: Multi-hop expansion of an impact set: Order-CONTAINS->OrderLine-CONTAINS->Product<-COMPONENT_OF-Part<-SUPPLIES-Supplier, Product-MADE_AT->Plant.
// kind: read
// params: {"order_ids": ["ORD-77202"]}
UNWIND $order_ids AS oid
MATCH (o:Order {id: oid})-[:CONTAINS]->(:OrderLine)-[:CONTAINS]->(pr:Product)
WITH DISTINCT pr
OPTIONAL MATCH (pr)-[:MADE_AT]->(pl:Plant)
OPTIONAL MATCH (pr)<-[:COMPONENT_OF]-(pt:Part)
OPTIONAL MATCH (pt)<-[:SUPPLIES]-(s:Supplier)
RETURN count(DISTINCT pr) AS products, count(DISTINCT pt) AS parts, count(DISTINCT s) AS suppliers,
       collect(DISTINCT pl.id) AS plants, collect(DISTINCT pr.id) AS product_ids
