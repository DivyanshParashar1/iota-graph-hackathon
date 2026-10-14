// name: exec_expedite
// purpose: Action effect EXPEDITE: flag orders as expedited, pull days_sched in by 2 and record the freight cost delta.
// kind: write
// params: {"ids": ["ORD-NONE"], "cost_per_order": 120.0, "aid": "ACT-example"}
UNWIND $ids AS oid
MATCH (o:Order {id: oid})
SET o.expedited = true, o.expedite_cost = $cost_per_order, o.expedited_by = $aid,
    o.days_sched = CASE WHEN o.days_sched > 2 THEN o.days_sched - 2 ELSE 0 END
RETURN count(o) AS expedited
