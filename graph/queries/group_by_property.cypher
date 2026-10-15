// name: group_by_property
// purpose: Count nodes of one generated type grouped by a property. Template: {label}, {prop}.
// graph: ops
// kind: template
// params: {"limit": 25}
MATCH (n:{label})
RETURN n.{prop} AS value, count(n) AS count
ORDER BY count DESC, value
LIMIT $limit
