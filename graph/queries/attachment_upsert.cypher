// name: attachment_upsert
// purpose: Record an upload with its profile
// graph: ops
// kind: write
// params: {"row": {"id": "ATT-1", "filename": "suppliers.csv", "mime": "text/csv", "bytes": 10, "sha256": "ab", "kind": "table", "profile_json": "{}", "text_path": "", "summary": "", "ts": 0}}
MERGE (a:_Attachment {id: $row.id})
SET a += $row
RETURN a.id AS id, a.filename AS filename
