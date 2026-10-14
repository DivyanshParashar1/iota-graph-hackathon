// name: record_episode
// purpose: Memory (episodic): MERGE an Episode for a closed incident and link the Playbook it USED; returns whether it was new.
// graph: mem
// kind: write
// params: {"id": "EPI-test", "incident_id": "INC-test", "type": "port_closure", "entity_ids": ["PORT-CNSHA"], "countries": ["CN"], "actions": ["REROUTE_ORDERS"], "outcome": "resolved", "before": 1.0, "after": 0.0, "summary": "test", "embedding": "$embed:test", "ts": 0, "playbook_id": "PB-test", "title": "test", "seeded": false, "recorded_at": 0}
MERGE (e:Episode {id: $id})
ON CREATE SET e.incident_id = $incident_id, e.disruption_type = $type, e.entity_ids = $entity_ids,
              e.countries = $countries, e.actions_taken = $actions, e.outcome = $outcome, e.revenue_before = $before,
              e.revenue_after = $after, e.summary = $summary, e.embedding = vecf32($embedding), e.ts = $ts,
              e.title = $title, e.seeded = $seeded, e.recorded_at = $recorded_at
WITH e
OPTIONAL MATCH (p:Playbook {id: $playbook_id})
FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END | MERGE (e)-[:USED]->(p))
RETURN e.id AS id, e.recorded_at = $recorded_at AS created
