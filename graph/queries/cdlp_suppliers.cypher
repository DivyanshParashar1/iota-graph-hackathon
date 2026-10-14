// name: cdlp_suppliers
// purpose: Community detection (label propagation) over the supplier network.
// kind: algo
// params: {}
CALL algo.labelPropagation({nodeLabels: ['Supplier'], relationshipTypes: ['SUPPLIES_TO']}) YIELD node, communityId
RETURN communityId AS cluster, count(node) AS size, collect(DISTINCT node.country) AS countries,
       collect(node.id) AS ids
ORDER BY size DESC
