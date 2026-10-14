// name: link_decision_about
// purpose: Ingest. Decision-[:ABOUT]->Supplier|Part|Port.
// kind: write
// params: {"rows": [{"decision_id": "DEC-TEST", "entity": "SUP-TEST"}]}
UNWIND $rows AS r
MATCH (d:Decision {id: r.decision_id})
OPTIONAL MATCH (s:Supplier {id: r.entity})
OPTIONAL MATCH (pt:Part {id: r.entity})
OPTIONAL MATCH (po:Port {id: r.entity})
OPTIONAL MATCH (pr:Product {id: r.entity})
OPTIONAL MATCH (e:Employee {id: r.entity})
OPTIONAL MATCH (l:Lane {id: r.entity})
WITH d, coalesce(s, pt, po, pr, e, l) AS ent
WHERE ent IS NOT NULL
MERGE (d)-[:ABOUT]->(ent)
