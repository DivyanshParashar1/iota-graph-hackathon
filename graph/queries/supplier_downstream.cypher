// name: supplier_downstream
// purpose: Tier-1 suppliers reachable downstream (SUPPLIES_TO*0..2) from each given supplier.
// kind: read
// params: {"ids": ["SUP-T2-0029"]}
UNWIND $ids AS sid
MATCH (s:Supplier {id: sid})-[:SUPPLIES_TO*0..2]->(t:Supplier)
RETURN s.id AS id, collect(DISTINCT t.id) AS downstream
