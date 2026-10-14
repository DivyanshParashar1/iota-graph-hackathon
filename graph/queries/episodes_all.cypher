// name: episodes_all
// purpose: Memory (episodic): every episode with its playbook (recall scoring runs in Python).
// graph: mem
// kind: read
// params: {}
MATCH (e:Episode)
OPTIONAL MATCH (e)-[:USED]->(p:Playbook)
RETURN e.id AS id, e.incident_id AS incident_id, e.disruption_type AS disruption_type, e.entity_ids AS entity_ids,
       e.countries AS countries, e.actions_taken AS actions_taken, e.outcome AS outcome,
       e.revenue_before AS revenue_before, e.revenue_after AS revenue_after, e.summary AS summary, e.ts AS ts,
       e.title AS title, e.seeded AS seeded, p.id AS playbook_id, p.name AS playbook, p.success_rate AS playbook_success_rate
ORDER BY e.ts DESC
