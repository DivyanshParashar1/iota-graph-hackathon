// name: expert_get
// purpose: One expert role by id
// graph: ops
// kind: read
// params: {"id": "EXP-1"}
MATCH (e:_ExpertRole {id: $id})
RETURN e.id AS id, e.name AS name, e.title AS title, e.mandate AS mandate, e.justification AS justification,
       e.system_prompt AS system_prompt, e.tools_json AS tools_json, e.focus_json AS focus_json,
       e.playbook_json AS playbook_json, e.status AS status, e.version AS version, e.origin AS origin,
       e.stale AS stale, e.ts AS ts
