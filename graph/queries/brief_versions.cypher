// name: brief_versions
// purpose: Every brief version, newest first (artifact history)
// graph: ops
// kind: read
// params: {}
MATCH (b:_Brief)
RETURN b.id AS id, b.version AS version, b.approved AS approved, b.stale AS stale, b.created_at AS created_at
ORDER BY b.version DESC
