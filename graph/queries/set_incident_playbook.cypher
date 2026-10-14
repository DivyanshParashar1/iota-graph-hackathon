// name: set_incident_playbook
// purpose: Write: record on the Incident blackboard which playbook the Planner is following and what Sentinel recalled.
// kind: write
// params: {"iid": "INC-example", "pid": "PB-port-closure", "recalled": ["EPI-example"]}
MATCH (i:Incident {id: $iid})
SET i.playbook_id = coalesce($pid, i.playbook_id), i.recalled_episodes = coalesce($recalled, i.recalled_episodes)
RETURN i.id AS id
