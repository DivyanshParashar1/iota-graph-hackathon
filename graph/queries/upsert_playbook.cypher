// name: upsert_playbook
// purpose: Memory (procedural): seed or update a Playbook.
// graph: mem
// kind: write
// params: {"rows": [{"id": "PB-test", "disruption_type": "port_closure", "name": "Test", "steps": ["REROUTE_ORDERS"], "uses": 1, "successes": 1}]}
UNWIND $rows AS r
MERGE (p:Playbook {id: r.id})
ON CREATE SET p.disruption_type = r.disruption_type, p.name = r.name, p.steps = r.steps, p.uses = r.uses,
              p.successes = r.successes, p.success_rate = toFloat(r.successes) / r.uses, p.description = r.description
RETURN count(p) AS n
