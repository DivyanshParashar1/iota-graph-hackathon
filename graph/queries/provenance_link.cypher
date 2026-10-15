// name: provenance_link
// purpose: Link generated instance nodes back to the form answers and uploads they came from
// graph: ops
// kind: write
// params: {"rows": [{"node_id": "SUP-1", "source_id": "ANS-1", "source": "user", "confidence": "exact", "ts": 0}]}
UNWIND $rows AS r
MATCH (n {id: r.node_id})
MATCH (src {id: r.source_id})
MERGE (p:_Provenance {id: 'PRV-' + r.node_id + '-' + r.source_id})
SET p.source = r.source, p.confidence = r.confidence, p.ts = r.ts
MERGE (n)-[:HAS_PROVENANCE]->(p)
MERGE (p)-[:FROM_SOURCE]->(src)
RETURN count(p) AS links
