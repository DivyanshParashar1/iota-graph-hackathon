// name: link_evidence
// purpose: Write: Action-[:BASED_ON {role}]->evidence node.
// kind: write
// params: {"aid": "ACT-example", "rows": [{"id": "PORT-CNSHA", "role": "disrupted"}]}
MATCH (a:Action {id: $aid})
UNWIND $rows AS r
WITH a, r, r.id AS x
OPTIONAL MATCH (n1:Order {id: x})
OPTIONAL MATCH (n2:Lane {id: x})
OPTIONAL MATCH (n3:Port {id: x})
OPTIONAL MATCH (n4:Supplier {id: x})
OPTIONAL MATCH (n5:Part {id: x})
OPTIONAL MATCH (n6:Product {id: x})
OPTIONAL MATCH (n7:Customer {id: x})
OPTIONAL MATCH (n8:Document {id: x})
OPTIONAL MATCH (n9:Chunk {id: x})
OPTIONAL MATCH (n10:Contract {id: x})
OPTIONAL MATCH (n11:Incident {id: x})
OPTIONAL MATCH (n12:Disruption {id: x})
OPTIONAL MATCH (n13:Employee {id: x})
OPTIONAL MATCH (n14:Decision {id: x})
OPTIONAL MATCH (n15:Plant {id: x})
OPTIONAL MATCH (n16:ChatMessage {id: x})
WITH a, r, x, coalesce(n1, n2, n3, n4, n5, n6, n7, n8, n9, n10, n11, n12, n13, n14, n15, n16) AS n
WHERE n IS NOT NULL
MERGE (a)-[b:BASED_ON]->(n)
SET b.role = r.role
RETURN count(n) AS linked
