// name: graph_edges_between
// purpose: The edges among a given set of instance node ids (the graph view's links)
// graph: ops
// kind: read
// params: {"ids": ["SUP-0001"], "limit": 1200}
MATCH (a)-[r]->(b)
WHERE a.id IN $ids AND b.id IN $ids
RETURN a.id AS source, type(r) AS type, b.id AS target
LIMIT $limit
