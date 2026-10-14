// name: undo_split_order
// purpose: Undo SPLIT_ORDER: delete the child order and restore the parent's value.
// kind: write
// params: {"oid": "ORD-NONE", "child": "ORD-NONE-S1", "total": 1.0}
MATCH (o:Order {id: $oid})
SET o.total = $total
WITH o
OPTIONAL MATCH (k:Order {id: $child})
DETACH DELETE k
RETURN o.id AS id
