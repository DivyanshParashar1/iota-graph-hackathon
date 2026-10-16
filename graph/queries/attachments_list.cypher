// name: attachments_list
// purpose: Every upload of this tenant with its profile
// graph: ops
// kind: read
// params: {}
MATCH (a:_Attachment)
RETURN a.id AS id, a.filename AS filename, a.mime AS mime, a.bytes AS bytes, a.sha256 AS sha256,
       a.kind AS kind, a.profile_json AS profile_json, a.summary AS summary,
       a.text_path AS text_path, a.path AS path, a.ts AS ts
ORDER BY a.ts
