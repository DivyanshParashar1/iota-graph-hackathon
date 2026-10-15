// name: graph_nodes_sample
// purpose: A sample of the generated instance nodes for the graph view (platform state excluded)
// graph: ops
// kind: read
// params: {"limit": 300}
MATCH (n)
WHERE NOT any(l IN labels(n) WHERE l STARTS WITH '_')
RETURN n.id AS id, labels(n)[0] AS label, coalesce(n.name, n.title, n.id) AS title
LIMIT $limit
