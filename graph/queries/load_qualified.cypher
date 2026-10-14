// name: load_qualified
// purpose: Ingest. Supplier-[:QUALIFIED_FOR]->Part (inactive alternates).
// kind: write
// params: {"rows": [{"supplier_id": "SUP-TEST", "part_id": "PRT-TEST", "qualified_on": "2025-01-01", "lead_time_days": 10, "unit_cost": 1.0}]}
UNWIND $rows AS r
MATCH (s:Supplier {id: r.supplier_id})
MATCH (pt:Part {id: r.part_id})
MERGE (s)-[x:QUALIFIED_FOR]->(pt)
SET x.qualified_on = r.qualified_on, x.lead_time_days = r.lead_time_days, x.unit_cost = r.unit_cost
