// name: neighbourhood
// purpose: One node's immediate neighbours and the edge types that reach them. Template: {label}.
// graph: ops
// kind: template
// params: {"id": "SUP-1", "limit": 50}
MATCH (n:{label} {{id: $id}})-[r]-(m)
WHERE NOT any(l IN labels(m) WHERE l STARTS WITH '_')
RETURN type(r) AS rel, startNode(r).id = n.id AS outgoing, labels(m)[0] AS label, m.id AS id,
       coalesce(m.name, m.title, m.id) AS title
ORDER BY rel, id
LIMIT $limit
