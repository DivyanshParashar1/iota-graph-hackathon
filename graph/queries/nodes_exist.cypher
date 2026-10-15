// name: nodes_exist
// purpose: Which of the given ids exist (any evidence-capable label, all index lookups).
// kind: read
// params: {"ids": ["PORT-CNSHA", "NOPE"]}
UNWIND $ids AS x
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
OPTIONAL MATCH (n17:Action {id: x})
OPTIONAL MATCH (n18:Team {id: x})
WITH x, coalesce(n1, n2, n3, n4, n5, n6, n7, n8, n9, n10, n11, n12, n13, n14, n15, n16, n17, n18) AS n
RETURN x AS id, n IS NOT NULL AS exists, CASE WHEN n IS NULL THEN NULL ELSE labels(n)[0] END AS label,
       CASE WHEN n IS NULL THEN NULL ELSE coalesce(n.name, n.title, n.id) END AS name
