// name: playbooks_list
// purpose: Memory inspector: all playbooks.
// graph: mem
// kind: read
// params: {}
MATCH (p:Playbook)
OPTIONAL MATCH (e:Episode)-[:USED]->(p)
RETURN p.id AS id, p.disruption_type AS disruption_type, p.name AS name, p.steps AS steps, p.uses AS uses,
       p.successes AS successes, p.success_rate AS success_rate, collect(e.id) AS episodes
ORDER BY p.disruption_type, p.success_rate DESC
