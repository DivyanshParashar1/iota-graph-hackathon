// name: supplier_exposure
// purpose: Open orders impacted by an incident that contain a part supplied by a given supplier.
// kind: read
// params: {"iid": "INC-example", "sid": "SUP-T1-0001"}
MATCH (i:Incident {id: $iid})-[:IMPACTS]->(o:Order {open: true})
MATCH (o)-[:CONTAINS]->(:OrderLine)-[:CONTAINS]->(:Product)<-[:COMPONENT_OF]-(:Part)<-[:SUPPLIES]-(s:Supplier {id: $sid})
WITH DISTINCT o
RETURN count(o) AS orders, sum(o.total) AS revenue
