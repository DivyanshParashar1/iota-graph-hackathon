// name: create_disruption
// purpose: Write: MERGE a Disruption by deterministic id and link it to the RiskBearing nodes it AFFECTS.
// kind: write
// params: {"id": "DIS-example", "type": "port_closure", "name": "Example", "severity": "high", "started_at": 0, "expected_days": 10, "source": "scenario", "targets": ["PORT-CNSHA"]}
MERGE (d:Disruption {id: $id})
ON CREATE SET d.type = $type, d.name = $name, d.severity = $severity, d.started_at = $started_at,
              d.expected_days = $expected_days, d.source = $source, d.active = true
WITH d
UNWIND $targets AS tid
OPTIONAL MATCH (p:Port {id: tid})
OPTIONAL MATCH (s:Supplier {id: tid})
OPTIONAL MATCH (l:Lane {id: tid})
WITH d, coalesce(p, s, l) AS t
WHERE t IS NOT NULL
MERGE (d)-[a:AFFECTS]->(t)
SET a.severity = d.severity, t.status = 'disrupted'
RETURN d.id AS id, d.type AS type, count(t) AS affects
