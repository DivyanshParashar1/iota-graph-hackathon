// name: brief_upsert
// purpose: Store a new version of the Supply Chain Brief (versions are never overwritten)
// graph: ops
// kind: write
// params: {"row": {"id": "BRF-1", "version": 1, "json": "{}", "approved": false, "stale": false, "created_at": 0}}
MERGE (b:_Brief {id: $row.id})
SET b += $row
RETURN b.id AS id, b.version AS version
