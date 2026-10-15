// name: supplier_network_version
// purpose: Cheap fingerprint of the supplier network (node and SUPPLIES_TO edge counts) used to invalidate cached algorithm results.
// kind: read
// params: {}
MATCH (s:Supplier)
OPTIONAL MATCH (s)-[r:SUPPLIES_TO]->()
RETURN count(DISTINCT s) AS suppliers, count(r) AS edges
