// name: blast_radius_port
// purpose: Q1. Blast radius of a port closure: Disruption-AFFECTS->Port<-ORIGIN|DEST-Lane<-SHIPS_VIA-Order(open)-PLACED_BY->Customer.
// kind: read
// params: {"did": "DIS-example"}
MATCH (d:Disruption {id: $did})-[:AFFECTS]->(port:Port)
MATCH (port)<-[:ORIGIN|DEST]-(lane:Lane)<-[:SHIPS_VIA]-(o:Order {open: true})
WITH DISTINCT o, lane
MATCH (o)-[:PLACED_BY]->(c:Customer)
RETURN count(o) AS orders_at_risk, sum(o.total) AS revenue_at_risk, count(DISTINCT c) AS customers_affected,
       collect(DISTINCT lane.id) AS lanes, collect([o.id, o.total]) AS orders
