// name: undo_reroute
// purpose: Undo REROUTE_ORDERS: put orders back on their original lane and schedule.
// kind: write
// params: {"rows": [{"order_id": "ORD-NONE", "from_lane": "LANE-X", "to_lane": "LANE-Y", "days_sched": 4}]}
UNWIND $rows AS r
MATCH (o:Order {id: r.order_id})-[x:SHIPS_VIA]->(:Lane {id: r.to_lane})
MATCH (old:Lane {id: r.from_lane})
DELETE x
CREATE (o)-[:SHIPS_VIA]->(old)
SET o.days_sched = r.days_sched
RETURN count(o) AS restored
