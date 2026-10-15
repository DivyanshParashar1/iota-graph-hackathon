// name: nodes_of_type
// purpose: Nodes of one generated type (paged). Template: {label}.
// graph: ops
// kind: template
// params: {"limit": 25, "skip": 0}
MATCH (n:{label})
RETURN n.id AS id, properties(n) AS properties
ORDER BY n.id
SKIP $skip
LIMIT $limit
