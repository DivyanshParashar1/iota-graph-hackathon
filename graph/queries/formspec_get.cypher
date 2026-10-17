// name: formspec_get
// purpose: One form round by id
// graph: ops
// kind: read
// params: {"id": "FRM-1"}
MATCH (f:_FormSpec {id: $id})
RETURN f.id AS id, f.round AS round, f.title AS title, f.intro AS intro, f.fields_json AS fields_json,
       f.status AS status, f.stale AS stale, f.ts AS ts
