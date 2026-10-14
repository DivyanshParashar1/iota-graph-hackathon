// name: get_playbook
// purpose: Memory (procedural): best playbook for a disruption type by success rate, then uses.
// graph: mem
// kind: read
// params: {"type": "port_closure"}
MATCH (p:Playbook {disruption_type: $type})
RETURN p.id AS id, p.name AS name, p.steps AS steps, p.uses AS uses, p.successes AS successes,
       p.success_rate AS success_rate, p.description AS description
ORDER BY p.success_rate DESC, p.uses DESC LIMIT 3
