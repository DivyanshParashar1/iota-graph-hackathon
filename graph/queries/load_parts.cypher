// name: load_parts
// purpose: Ingest. Upsert parts.
// kind: write
// params: {"rows": [{"id": "PRT-TEST", "name": "Test part", "category": "Test", "department": "Test", "unit_cost": 1.0, "criticality": "low"}]}
UNWIND $rows AS r
MERGE (p:Part {id: r.id})
SET p.name = r.name, p.category = r.category, p.department = r.department, p.unit_cost = r.unit_cost,
    p.criticality = r.criticality
