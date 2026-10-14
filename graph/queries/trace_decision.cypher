// name: trace_decision
// purpose: Q7. Trace decisions ABOUT entities to their sources (documents and chat messages) and the people involved.
// kind: read
// params: {"ids": ["PRT-0075"]}
MATCH (dec:Decision)-[:ABOUT]->(x)
WHERE x.id IN $ids
MATCH (dec)-[:SOURCED_FROM]->(src)
OPTIONAL MATCH (author:Employee)-[:AUTHORED|POSTED]->(src)
OPTIONAL MATCH (th:Thread)-[:HAS_MSG]->(src)
OPTIONAL MATCH (th)-[:THREAD_DOC]->(td:Document)
OPTIONAL MATCH (p:Employee)-[:PARTICIPATED_IN]->(dec)
RETURN dec.id AS decision_id, dec.summary AS summary, dec.decided_at AS decided_at, labels(src)[0] AS source_type,
       src.id AS source_id, coalesce(src.title, src.text) AS source_text, coalesce(src.uri, td.uri) AS uri,
       td.id AS thread_doc, collect(DISTINCT author.name) AS authors, collect(DISTINCT p.name) AS people
ORDER BY decided_at DESC
