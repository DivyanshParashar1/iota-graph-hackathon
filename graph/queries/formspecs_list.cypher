// name: formspecs_list
// purpose: Every form round in order
// graph: ops
// kind: read
// params: {}
MATCH (f:_FormSpec)
RETURN f.id AS id, f.round AS round, f.title AS title, f.intro AS intro, f.fields_json AS fields_json,
       f.status AS status, f.stale AS stale, f.ts AS ts
ORDER BY f.round, f.ts
