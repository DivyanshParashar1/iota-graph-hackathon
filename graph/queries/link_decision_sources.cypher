// name: link_decision_sources
// purpose: Ingest. Decision-[:SOURCED_FROM]->Document|ChatMessage.
// kind: write
// params: {"rows": [{"decision_id": "DEC-TEST", "src": "DOC-TEST"}]}
UNWIND $rows AS r
MATCH (d:Decision {id: r.decision_id})
OPTIONAL MATCH (doc:Document {id: r.src})
OPTIONAL MATCH (m:ChatMessage {id: r.src})
WITH d, coalesce(doc, m) AS src
WHERE src IS NOT NULL
MERGE (d)-[:SOURCED_FROM]->(src)
