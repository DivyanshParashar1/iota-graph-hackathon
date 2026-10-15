// name: formspec_upsert
// purpose: Store one round of the data agent's in-chat form
// graph: ops
// kind: write
// params: {"row": {"id": "FRM-1", "round": 1, "title": "t", "intro": "", "fields_json": "[]", "status": "open", "ts": 0}}
MERGE (f:_FormSpec {id: $row.id})
SET f += $row
RETURN f.id AS id, f.round AS round, f.status AS status
