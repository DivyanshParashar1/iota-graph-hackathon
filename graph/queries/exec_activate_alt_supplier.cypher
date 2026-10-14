// name: exec_activate_alt_supplier
// purpose: Action effect ACTIVATE_ALT_SUPPLIER: turn QUALIFIED_FOR into SUPPLIES {share} and scale down the existing suppliers' shares.
// kind: write
// params: {"aid": "ACT-example", "pid": "PRT-NONE", "sid": "SUP-NONE", "share": 0.3}
MATCH (s:Supplier {id: $sid})-[q:QUALIFIED_FOR]->(pt:Part {id: $pid})
OPTIONAL MATCH (pt)<-[old:SUPPLIES]-(:Supplier)
SET old.share = round(old.share * (1 - $share) * 10000) / 10000.0
WITH DISTINCT s, q, pt
MERGE (s)-[n:SUPPLIES]->(pt)
SET n.lead_time_days = q.lead_time_days, n.unit_cost = q.unit_cost, n.share = $share, n.activated_by = $aid
DELETE q
RETURN s.id AS supplier_id, pt.id AS part_id
