// name: related_suppliers
// purpose: Suppliers related to an incident's disruption: those shipping from an affected port, or the failed supplier and its tier-1 customers; contract holders first.
// kind: read
// params: {"iid": "INC-example", "limit": 3}
MATCH (i:Incident {id: $iid})<-[:TRIGGERED]-(d:Disruption)
CALL {
  WITH d
  MATCH (d)-[:AFFECTS]->(:Port)<-[:SHIPS_FROM]-(s:Supplier {tier: 1})
  RETURN s
  UNION
  WITH d
  MATCH (d)-[:AFFECTS]->(s0:Supplier)-[:SUPPLIES_TO*0..2]->(s:Supplier {tier: 1})
  RETURN s
}
WITH DISTINCT s
OPTIONAL MATCH (k:Contract)-[:WITH]->(s)
RETURN s.id AS id, s.name AS name, s.country AS country, k.id AS contract_id
ORDER BY CASE WHEN k IS NULL THEN 1 ELSE 0 END, s.capacity DESC, s.id LIMIT $limit
