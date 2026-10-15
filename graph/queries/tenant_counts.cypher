// name: tenant_counts
// purpose: Node and edge totals of a graph
// graph: ops
// kind: read
// params: {}
MATCH (n)
WITH count(n) AS nodes
OPTIONAL MATCH ()-[r]->()
RETURN nodes, count(r) AS edges
