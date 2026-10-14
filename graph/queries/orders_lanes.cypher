// name: orders_lanes
// purpose: Current lane and schedule of the given orders (before-state for reroutes).
// kind: read
// params: {"ids": ["ORD-77202"]}
UNWIND $ids AS oid
MATCH (o:Order {id: oid})-[:SHIPS_VIA]->(l:Lane)
RETURN o.id AS order_id, l.id AS lane_id, o.days_sched AS days_sched, o.status AS status, o.total AS total
