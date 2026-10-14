// name: load_order_lane
// purpose: Ingest. Order-[:SHIPS_VIA]->Lane (only for orders that are loaded).
// kind: write
// params: {"rows": [{"order_id": "ORD-TEST", "lane_id": "LANE-TEST"}]}
UNWIND $rows AS r
MATCH (o:Order {id: r.order_id})
MATCH (l:Lane {id: r.lane_id})
MERGE (o)-[:SHIPS_VIA]->(l)
