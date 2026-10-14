// name: alt_route
// purpose: Q10c. Weighted k-shortest sea routes over CONNECTS (algo.SPpaths, weight transit_days), dropping any route through an avoided port.
// kind: algo
// params: {"from": "PORT-CNNGB", "to": "PORT-USLAX", "avoid": ["PORT-CNSHA"]}
MATCH (a:Port {id: $from}), (b:Port {id: $to})
CALL algo.SPpaths({sourceNode: a, targetNode: b, relTypes: ['CONNECTS'], weightProp: 'transit_days', maxLen: 6, pathCount: 20})
YIELD path, pathWeight
WITH path, pathWeight WHERE NONE(n IN nodes(path) WHERE n.id IN $avoid)
RETURN [n IN nodes(path) | n.id] AS route, pathWeight AS transit_days
ORDER BY transit_days LIMIT 3
