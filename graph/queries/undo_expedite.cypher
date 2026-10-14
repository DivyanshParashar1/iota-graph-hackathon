// name: undo_expedite
// purpose: Undo EXPEDITE: restore schedule and clear the expedite flag.
// kind: write
// params: {"rows": [{"order_id": "ORD-NONE", "days_sched": 4}]}
UNWIND $rows AS r
MATCH (o:Order {id: r.order_id})
SET o.days_sched = r.days_sched, o.expedited = false, o.expedite_cost = 0.0
RETURN count(o) AS restored
