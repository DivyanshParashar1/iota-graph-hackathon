// name: exec_reroute
// purpose: Action effect REROUTE_ORDERS: re-point SHIPS_VIA from the disrupted lane to an alternate lane (created if needed) and push days_sched.
// kind: write
// params: {"aid": "ACT-example", "moves": [{"from_lane": "LANE-X", "to_lane": "LANE-Y", "to_origin": "PORT-CNNGB", "to_dest": "PORT-USLAX", "mode": "Standard Class", "carrier": "Northstar Freight", "transit_days": 18.0, "added_days": 1, "order_ids": ["ORD-NONE"]}]}
UNWIND $moves AS m
MERGE (nl:Lane {id: m.to_lane})
ON CREATE SET nl:RiskBearing, nl.mode = m.mode, nl.transit_days = m.transit_days, nl.carrier = m.carrier,
              nl.risk_score = 0.2, nl.created_by = $aid
WITH m, nl
MATCH (po:Port {id: m.to_origin})
MATCH (pd:Port {id: m.to_dest})
MERGE (nl)-[:ORIGIN]->(po)
MERGE (nl)-[:DEST]->(pd)
WITH m, nl
UNWIND m.order_ids AS oid
MATCH (o:Order {id: oid})-[r:SHIPS_VIA]->(old:Lane {id: m.from_lane})
DELETE r
CREATE (o)-[:SHIPS_VIA]->(nl)
SET o.days_sched = o.days_sched + m.added_days
RETURN count(o) AS moved
