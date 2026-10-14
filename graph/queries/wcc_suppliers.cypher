// name: wcc_suppliers
// purpose: Weakly connected components of the supplier network (correlated risk groups).
// kind: algo
// params: {}
CALL algo.WCC({nodeLabels: ['Supplier'], relationshipTypes: ['SUPPLIES_TO']}) YIELD node, componentId
RETURN componentId AS cluster, count(node) AS size, collect(DISTINCT node.country) AS countries,
       collect(node.id) AS ids
ORDER BY size DESC
