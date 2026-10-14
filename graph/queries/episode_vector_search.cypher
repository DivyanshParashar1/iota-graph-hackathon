// name: episode_vector_search
// purpose: Memory (episodic): vector distance between a query and episode summaries (lower = closer).
// graph: mem
// kind: read
// params: {"qvec": "$embed:port closure at Shanghai", "k": 50}
CALL db.idx.vector.queryNodes('Episode', 'embedding', $k, vecf32($qvec)) YIELD node, score
RETURN node.id AS id, score AS distance
