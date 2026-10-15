// name: brief_current
// purpose: The latest brief version
// graph: ops
// kind: read
// params: {}
MATCH (b:_Brief)
RETURN b.id AS id, b.version AS version, b.json AS json, b.approved AS approved, b.stale AS stale,
       b.created_at AS created_at
ORDER BY b.version DESC
LIMIT 1
