// name: write_impacts
// purpose: Write: Incident-[:IMPACTS {revenue}]->Order for the impact set.
// kind: write
// params: {"iid": "INC-example", "rows": [{"id": "ORD-77202", "revenue": 1.0}]}
MATCH (i:Incident {id: $iid})
UNWIND $rows AS r
MATCH (o:Order {id: r.id})
MERGE (i)-[x:IMPACTS]->(o)
SET x.revenue = r.revenue
