// name: meta_stats
// purpose: Label and relationship-type counts for the ontology page (db.meta.stats()).
// kind: read
// params: {}
CALL db.meta.stats() YIELD labels, relTypes, nodeCount, relCount
RETURN labels, relTypes, nodeCount, relCount
