// name: single_sourced_parts
// purpose: Q3. Single-sourced parts (exactly one active supplier) and how many products depend on each.
// kind: read
// params: {"limit": 50}
MATCH (pt:Part)<-[:SUPPLIES]-(s:Supplier)
WITH pt, count(s) AS n, collect(s) AS sups
WHERE n = 1
MATCH (pt)-[:COMPONENT_OF]->(pr:Product)
RETURN pt.id AS part_id, pt.name AS part, pt.criticality AS criticality, sups[0].id AS sole_supplier_id,
       sups[0].name AS sole_supplier, count(pr) AS products_dependent
ORDER BY products_dependent DESC, part_id LIMIT $limit
