// name: playbook_outcome
// purpose: Memory (procedural): count one more use (and success) of a playbook and refresh its success rate.
// graph: mem
// kind: write
// params: {"id": "PB-test", "success": 1}
MATCH (p:Playbook {id: $id})
SET p.uses = p.uses + 1, p.successes = p.successes + $success
SET p.success_rate = toFloat(p.successes) / p.uses
RETURN p.id AS id, p.uses AS uses, p.successes AS successes, p.success_rate AS success_rate
