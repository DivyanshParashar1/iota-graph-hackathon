// name: owner_sources
// purpose: Documents that support an ownership answer: the supplier's contract and chat messages mentioning both the supplier and the owner.
// kind: read
// params: {"sid": "SUP-T1-0001", "eid": "EMP-001"}
MATCH (s:Supplier {id: $sid})
OPTIONAL MATCH (k:Contract)-[:WITH]->(s)
OPTIONAL MATCH (k)-[:DOCUMENTED_IN]->(d:Document)
OPTIONAL MATCH (m:ChatMessage)-[:MENTIONS]->(s)
WHERE (m)-[:MENTIONS]->(:Employee {id: $eid}) OR (:Employee {id: $eid})-[:POSTED]->(m)
OPTIONAL MATCH (th:Thread)-[:HAS_MSG]->(m)
OPTIONAL MATCH (th)-[:THREAD_DOC]->(td:Document)
RETURN d.id AS contract_doc, d.title AS contract_title, d.uri AS contract_uri,
       collect(DISTINCT {msg: m.id, text: m.text, ts: m.ts, doc: td.id, title: td.title, uri: td.uri}) AS messages
