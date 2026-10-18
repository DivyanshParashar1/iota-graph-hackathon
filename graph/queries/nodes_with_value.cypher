// name: nodes_with_value
// purpose: Nodes of one generated type whose property equals a value (an overview hot spot's examples). Template: {label}, {prop}.
// graph: ops
// kind: template
// params: {"value": "delayed", "limit": 5}
MATCH (n:{label})
WHERE n.{prop} = $value
RETURN n.id AS id, properties(n) AS properties
ORDER BY n.id
LIMIT $limit
