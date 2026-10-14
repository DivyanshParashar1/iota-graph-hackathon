// name: exec_place_hold
// purpose: Action effect PLACE_HOLD: set orders ON_HOLD with a reason (still open, still at risk).
// kind: write
// params: {"ids": ["ORD-NONE"], "reason": "supplier failure", "aid": "ACT-example"}
UNWIND $ids AS oid
MATCH (o:Order {id: oid})
SET o.status = 'ON_HOLD', o.hold_reason = $reason, o.held_by = $aid
RETURN count(o) AS held
