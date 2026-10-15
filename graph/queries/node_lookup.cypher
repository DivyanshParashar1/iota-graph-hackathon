// name: node_lookup
// purpose: One node of a generated type by id, with every property. Template: {label}.
// graph: ops
// kind: template
// params: {"id": "SUP-1"}
MATCH (n:{label} {{id: $id}})
RETURN n.id AS id, labels(n) AS labels, properties(n) AS properties
