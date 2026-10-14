// name: load_product_plant
// purpose: Ingest. Product-[:MADE_AT]->Plant.
// kind: write
// params: {"rows": [{"product_id": "PRD-TEST", "plant_id": "PLT-TEST"}]}
UNWIND $rows AS r
MATCH (p:Product {id: r.product_id})
MATCH (pl:Plant {id: r.plant_id})
MERGE (p)-[:MADE_AT]->(pl)
