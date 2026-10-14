// name: blast_radius_carrier
// purpose: Blast radius of a carrier strike: Disruption-AFFECTS->Lane<-SHIPS_VIA-Order(open)-PLACED_BY->Customer.
// kind: read
// params: {"did": "DIS-example"}
MATCH (d:Disruption {id: $did})-[:AFFECTS]->(lane:Lane)<-[:SHIPS_VIA]-(o:Order {open: true})
MATCH (o)-[:PLACED_BY]->(c:Customer)
RETURN count(DISTINCT o) AS orders_at_risk, sum(o.total) AS revenue_at_risk, count(DISTINCT c) AS customers_affected,
       collect(DISTINCT lane.id) AS lanes, collect([o.id, o.total]) AS orders
