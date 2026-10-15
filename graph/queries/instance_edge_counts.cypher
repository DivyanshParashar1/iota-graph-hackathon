// name: instance_edge_counts
// purpose: Instance edge counts per generated relationship type (platform edges excluded)
// graph: ops
// kind: read
// params: {}
MATCH (a)-[r]->(b)
WHERE NOT any(l IN labels(a) WHERE l STARTS WITH '_') AND NOT any(l IN labels(b) WHERE l STARTS WITH '_')
RETURN type(r) AS rel, count(r) AS count
ORDER BY count DESC, rel
