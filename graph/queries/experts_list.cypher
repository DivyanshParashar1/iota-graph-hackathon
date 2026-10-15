// name: experts_list
// purpose: Every expert role, newest first
// graph: ops
// kind: read
// params: {}
MATCH (e:_ExpertRole)
RETURN e.id AS id, e.name AS name, e.title AS title, e.mandate AS mandate, e.justification AS justification,
       e.system_prompt AS system_prompt, e.tools_json AS tools_json, e.focus_json AS focus_json,
       e.playbook_json AS playbook_json, e.status AS status, e.version AS version, e.origin AS origin,
       e.stale AS stale, e.ts AS ts
ORDER BY e.ts DESC, e.name
