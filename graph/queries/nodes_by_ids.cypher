// name: nodes_by_ids
// purpose: Instance nodes by id whatever their generated type (an option's live impact); never platform nodes
// graph: ops
// kind: read
// params: {"ids": ["SUP-0001"]}
MATCH (n)
WHERE n.id IN $ids AND NOT any(l IN labels(n) WHERE l STARTS WITH '_')
RETURN labels(n)[0] AS label, n.id AS id, coalesce(n.name, n.title, n.id) AS title, properties(n) AS properties
ORDER BY id
