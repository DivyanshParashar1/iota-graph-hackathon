// name: expert_upsert
// purpose: Create or update an expert role (generated or user-authored)
// graph: ops
// kind: write
// params: {"row": {"id": "EXP-1", "name": "sourcing_risk", "title": "Sourcing Risk Analyst", "mandate": "", "justification": "", "system_prompt": "", "tools_json": "[]", "focus_json": "{}", "playbook_json": "[]", "status": "draft", "version": 1, "origin": "generated", "stale": false, "ts": 0}}
MERGE (e:_ExpertRole {id: $row.id})
SET e += $row
RETURN e.id AS id, e.name AS name, e.status AS status
