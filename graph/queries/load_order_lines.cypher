// name: load_order_lines
// purpose: Ingest. Upsert order lines, Order-[:CONTAINS]->OrderLine-[:CONTAINS]->Product.
// kind: write
// params: {"rows": [{"id": "OL-TEST", "order_id": "ORD-TEST", "product_id": "PRD-TEST", "qty": 1, "total": 1.0, "price": 1.0}]}
UNWIND $rows AS r
MATCH (o:Order {id: r.order_id})
MATCH (p:Product {id: r.product_id})
MERGE (l:OrderLine {id: r.id})
SET l.qty = r.qty, l.total = r.total, l.price = r.price
MERGE (o)-[:CONTAINS]->(l)
MERGE (l)-[:CONTAINS]->(p)
