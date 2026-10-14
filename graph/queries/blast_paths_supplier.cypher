// name: blast_paths_supplier
// purpose: Highlight subgraph for a supplier failure: SUPPLIES_TO chains from the failed supplier to the impacted parts and their products.
// kind: read
// params: {"did": "DIS-example", "parts": ["PRT-0001"]}
MATCH (d:Disruption {id: $did})-[:AFFECTS]->(s0:Supplier)
MATCH path = (s0)-[:SUPPLIES_TO*0..2]->(s1:Supplier)
WITH d, s0, s1, [n IN nodes(path) | n.id] AS chain
MATCH (s1)-[:SUPPLIES]->(pt:Part)
WHERE pt.id IN $parts
MATCH (pt)-[:COMPONENT_OF]->(pr:Product)
RETURN d.id AS d, chain, pt.id AS part, collect(DISTINCT pr.id) AS products
