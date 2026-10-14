// name: supplier_part_state
// purpose: Before-state for a supplier switch: active SUPPLIES shares and the QUALIFIED_FOR link.
// kind: read
// params: {"pid": "PRT-0075", "sid": "SUP-T1-0095"}
MATCH (pt:Part {id: $pid})
OPTIONAL MATCH (pt)<-[x:SUPPLIES]-(s:Supplier)
OPTIONAL MATCH (pt)<-[q:QUALIFIED_FOR]-(alt:Supplier {id: $sid})
RETURN collect(DISTINCT {supplier_id: s.id, share: x.share}) AS shares, q.qualified_on AS qualified_on,
       q.lead_time_days AS lead_time_days, q.unit_cost AS unit_cost
