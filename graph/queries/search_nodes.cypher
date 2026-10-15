// name: search_nodes
// purpose: Case-insensitive substring search over the title property of one generated type. Template: {label}, {prop}.
// graph: ops
// kind: template
// params: {"q": "acme", "limit": 20}
MATCH (n:{label})
WHERE toLower(toString(coalesce(n.{prop}, ''))) CONTAINS toLower($q) OR toLower(n.id) CONTAINS toLower($q)
RETURN n.id AS id, properties(n) AS properties
ORDER BY n.id
LIMIT $limit
