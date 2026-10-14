// name: load_products
// purpose: Ingest. Upsert DataCo products.
// kind: write
// params: {"rows": [{"id": "PRD-TEST", "name": "Test product", "category": "Test", "department": "Test", "price": 1.0}]}
UNWIND $rows AS r
MERGE (p:Product {id: r.id})
SET p.name = r.name, p.category = r.category, p.department = r.department, p.price = r.price
