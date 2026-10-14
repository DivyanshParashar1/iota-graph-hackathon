// name: lanes_get
// purpose: Lanes by id with their origin and destination ports (reroute planning).
// kind: read
// params: {"ids": ["LANE-CNSHA-USLAX-STD"]}
UNWIND $ids AS lid
MATCH (l:Lane {id: lid})-[:ORIGIN]->(o:Port)
MATCH (l)-[:DEST]->(d:Port)
RETURN l.id AS id, l.mode AS mode, l.carrier AS carrier, l.transit_days AS transit_days, o.id AS origin, d.id AS dest
