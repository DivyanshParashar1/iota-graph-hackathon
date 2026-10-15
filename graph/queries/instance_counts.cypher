// name: instance_counts
// purpose: Instance node counts per generated label (platform labels excluded)
// graph: ops
// kind: read
// params: {}
MATCH (n)
WITH labels(n)[0] AS label, count(n) AS count
WHERE NOT label STARTS WITH '_'
RETURN label, count
ORDER BY count DESC, label
