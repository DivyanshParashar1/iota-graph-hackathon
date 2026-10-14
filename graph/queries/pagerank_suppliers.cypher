// name: pagerank_suppliers
// purpose: Q10b. PageRank over SUPPLIES_TO: suppliers that many important suppliers feed into.
// kind: algo
// params: {"top_k": 10}
CALL algo.pageRank('Supplier', 'SUPPLIES_TO') YIELD node, score
RETURN node.id AS id, node.name AS name, node.tier AS tier, node.country AS country, score
ORDER BY score DESC LIMIT $top_k
