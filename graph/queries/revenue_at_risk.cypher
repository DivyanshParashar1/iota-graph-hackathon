// name: revenue_at_risk
// purpose: Live revenue at risk for an incident: union of the port, lane and supplier impact definitions, recomputed on every call (respects reroutes and supplier switches).
// kind: read
// params: {"iid": "INC-example"}
MATCH (i:Incident {id: $iid})<-[:TRIGGERED]-(d:Disruption)
CALL {
  WITH d
  MATCH (d)-[:AFFECTS]->(:Port)<-[:ORIGIN|DEST]-(:Lane)<-[:SHIPS_VIA]-(o:Order {open: true})
  RETURN o
  UNION
  WITH d
  MATCH (d)-[:AFFECTS]->(:Lane)<-[:SHIPS_VIA]-(o:Order {open: true})
  RETURN o
  UNION
  WITH d
  MATCH (d)-[:AFFECTS]->(s0:Supplier)
  MATCH (s0)-[:SUPPLIES_TO*0..2]->(s1:Supplier)
  WITH collect(DISTINCT s1) AS affected
  UNWIND affected AS a
  MATCH (a)-[:SUPPLIES]->(pt:Part)
  WITH DISTINCT pt, affected
  MATCH (pt)<-[:SUPPLIES]-(x:Supplier)
  WITH pt, affected, collect(x) AS sups
  WHERE all(y IN sups WHERE y IN affected)
  MATCH (pt)-[:COMPONENT_OF]->(:Product)<-[:CONTAINS]-(:OrderLine)<-[:CONTAINS]-(o:Order {open: true})
  RETURN o
}
WITH DISTINCT o
RETURN count(o) AS orders, sum(o.total) AS revenue, collect(o.id) AS order_ids
