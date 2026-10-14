// name: undo_activate_alt_supplier
// purpose: Undo ACTIVATE_ALT_SUPPLIER: drop the new SUPPLIES, restore QUALIFIED_FOR and the old shares.
// kind: write
// params: {"pid": "PRT-NONE", "sid": "SUP-NONE", "qualified_on": "2025-01-01", "lead_time_days": 20, "unit_cost": 1.0, "shares": []}
MATCH (s:Supplier {id: $sid})-[n:SUPPLIES]->(pt:Part {id: $pid})
DELETE n
MERGE (s)-[q:QUALIFIED_FOR]->(pt)
SET q.qualified_on = $qualified_on, q.lead_time_days = $lead_time_days, q.unit_cost = $unit_cost
WITH pt
UNWIND $shares AS r
MATCH (x:Supplier {id: r.supplier_id})-[e:SUPPLIES]->(pt)
SET e.share = r.share
RETURN count(e) AS restored
