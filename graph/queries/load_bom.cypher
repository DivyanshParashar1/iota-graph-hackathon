// name: load_bom
// purpose: Ingest. Part-[:COMPONENT_OF {qty}]->Product.
// kind: write
// params: {"rows": [{"part_id": "PRT-TEST", "product_id": "PRD-TEST", "qty": 1}]}
UNWIND $rows AS r
MATCH (pt:Part {id: r.part_id})
MATCH (pr:Product {id: r.product_id})
MERGE (pt)-[c:COMPONENT_OF]->(pr)
SET c.qty = r.qty
