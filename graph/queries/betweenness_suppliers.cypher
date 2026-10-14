// name: betweenness_suppliers
// purpose: Q10a. Exact betweenness centrality over the supplier network (SUPPLIES_TO; samplingSize above the node count = every source): chokepoints sit between many tier-3 and tier-1 suppliers.
// kind: algo
// params: {"top_k": 10}
CALL algo.betweenness({nodeLabels: ['Supplier'], relationshipTypes: ['SUPPLIES_TO'], samplingSize: 100000, samplingSeed: 42}) YIELD node, score
RETURN node.id AS id, node.name AS name, node.tier AS tier, node.country AS country, score
ORDER BY score DESC LIMIT $top_k
