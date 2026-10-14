// name: blast_radius_supplier
// purpose: Q2. Blast radius of a supplier failure: affected = failed supplier + SUPPLIES_TO*0..2 downstream; parts whose every active supplier is affected; their products' open orders.
// kind: read
// params: {"did": "DIS-example"}
MATCH (d:Disruption {id: $did})-[:AFFECTS]->(s0:Supplier)
MATCH (s0)-[:SUPPLIES_TO*0..2]->(s1:Supplier)
WITH collect(DISTINCT s1) AS affected
UNWIND affected AS a
MATCH (a)-[:SUPPLIES]->(pt:Part)
WITH DISTINCT pt, affected
MATCH (pt)<-[:SUPPLIES]-(x:Supplier)
WITH pt, affected, collect(x) AS sups
WITH affected, collect(CASE WHEN all(y IN sups WHERE y IN affected) THEN pt END) AS impacted,
     collect(CASE WHEN all(y IN sups WHERE y IN affected) THEN NULL ELSE pt.id END) AS degraded
UNWIND impacted AS pt
MATCH (pt)-[:COMPONENT_OF]->(pr:Product)<-[:CONTAINS]-(:OrderLine)<-[:CONTAINS]-(o:Order {open: true})
WITH affected, degraded, collect(DISTINCT pt.id) AS parts, collect(DISTINCT pr.id) AS products, collect(DISTINCT o) AS os
UNWIND os AS o
MATCH (o)-[:PLACED_BY]->(c:Customer)
RETURN count(o) AS orders_at_risk, sum(o.total) AS revenue_at_risk, count(DISTINCT c) AS customers_affected,
       collect([o.id, o.total]) AS orders, parts, products, degraded, [a IN affected | a.id] AS suppliers
