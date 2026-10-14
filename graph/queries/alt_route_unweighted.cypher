// name: alt_route_unweighted
// purpose: Fallback route: unweighted shortestPath over CONNECTS inside WITH, rejected if it touches an avoided port.
// kind: algo
// params: {"from": "PORT-CNNGB", "to": "PORT-USLAX", "avoid": ["PORT-CNSHA"]}
MATCH (a:Port {id: $from}), (b:Port {id: $to})
WITH shortestPath((a)-[:CONNECTS*..6]->(b)) AS p
WHERE p IS NOT NULL AND NONE(n IN nodes(p) WHERE n.id IN $avoid)
RETURN [n IN nodes(p) | n.id] AS route, reduce(t = 0.0, r IN relationships(p) | t + r.transit_days) AS transit_days
