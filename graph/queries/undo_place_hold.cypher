// name: undo_place_hold
// purpose: Undo PLACE_HOLD: restore each order's previous status.
// kind: write
// params: {"rows": [{"order_id": "ORD-NONE", "status": "PENDING"}]}
UNWIND $rows AS r
MATCH (o:Order {id: r.order_id})
SET o.status = r.status, o.hold_reason = NULL, o.held_by = NULL
RETURN count(o) AS restored
