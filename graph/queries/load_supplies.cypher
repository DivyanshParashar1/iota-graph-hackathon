// name: load_supplies
// purpose: Ingest. Supplier-[:SUPPLIES {lead_time_days, unit_cost, share}]->Part.
// kind: write
// params: {"rows": [{"supplier_id": "SUP-TEST", "part_id": "PRT-TEST", "lead_time_days": 10, "unit_cost": 1.0, "share": 1.0}]}
UNWIND $rows AS r
MATCH (s:Supplier {id: r.supplier_id})
MATCH (pt:Part {id: r.part_id})
MERGE (s)-[x:SUPPLIES]->(pt)
SET x.lead_time_days = r.lead_time_days, x.unit_cost = r.unit_cost, x.share = r.share
