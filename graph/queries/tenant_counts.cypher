// name: tenant_counts
// purpose: Node and relationship totals for a tenant graph.
// kind: read
// params: {}
CALL db.meta.stats() YIELD nodeCount, relCount
RETURN nodeCount AS nodes, relCount AS edges
