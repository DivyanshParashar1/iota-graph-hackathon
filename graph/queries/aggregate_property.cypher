// name: aggregate_property
// purpose: count / sum / avg / min / max of one property of one generated type. Template: {label}, {prop}.
// graph: ops
// kind: template
// params: {}
MATCH (n:{label})
RETURN count(n) AS count, sum(n.{prop}) AS sum, avg(n.{prop}) AS avg, min(n.{prop}) AS min, max(n.{prop}) AS max
