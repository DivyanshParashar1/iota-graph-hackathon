// name: handoff
// purpose: Write: Agent-[:HANDED_OFF_TO {incident_id, ts, summary}]->Agent (one edge per incident and pair, idempotent).
// kind: write
// params: {"src": "sentinel", "dst": "analyst", "iid": "INC-example", "ts": 0, "summary": ""}
MERGE (a:Agent {name: $src})
ON CREATE SET a.id = 'AGT-' + $src
MERGE (b:Agent {name: $dst})
ON CREATE SET b.id = 'AGT-' + $dst
MERGE (a)-[h:HANDED_OFF_TO {incident_id: $iid}]->(b)
SET h.ts = $ts, h.summary = $summary
RETURN a.name AS src, b.name AS dst
