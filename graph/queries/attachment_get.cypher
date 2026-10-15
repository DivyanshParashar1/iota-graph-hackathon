// name: attachment_get
// purpose: One upload by id
// graph: ops
// kind: read
// params: {"id": "ATT-1"}
MATCH (a:_Attachment {id: $id})
RETURN a.id AS id, a.filename AS filename, a.mime AS mime, a.bytes AS bytes, a.sha256 AS sha256,
       a.kind AS kind, a.profile_json AS profile_json, a.summary AS summary, a.text_path AS text_path, a.ts AS ts
