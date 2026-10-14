// name: load_mentions
// purpose: Ingest. Chunk|ChatMessage-[:MENTIONS {confidence}]->entity (Supplier, Part, Port, Product, Employee, Lane).
// kind: write
// params: {"rows": [{"src": "DOC-TEST#0", "dst": "SUP-TEST", "confidence": 1.0}]}
UNWIND $rows AS r
OPTIONAL MATCH (c:Chunk {id: r.src})
OPTIONAL MATCH (m:ChatMessage {id: r.src})
WITH r, coalesce(c, m) AS src
WHERE src IS NOT NULL
OPTIONAL MATCH (s:Supplier {id: r.dst})
OPTIONAL MATCH (pt:Part {id: r.dst})
OPTIONAL MATCH (po:Port {id: r.dst})
OPTIONAL MATCH (pr:Product {id: r.dst})
OPTIONAL MATCH (e:Employee {id: r.dst})
OPTIONAL MATCH (l:Lane {id: r.dst})
WITH r, src, coalesce(s, pt, po, pr, e, l) AS ent
WHERE ent IS NOT NULL
MERGE (src)-[x:MENTIONS]->(ent)
SET x.confidence = CASE WHEN x.confidence IS NULL OR r.confidence > x.confidence THEN r.confidence ELSE x.confidence END
