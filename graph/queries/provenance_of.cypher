// name: provenance_of
// purpose: Where did this number come from? The answers and uploads behind one instance node
// graph: ops
// kind: read
// params: {"id": "SUP-1"}
MATCH (n {id: $id})-[:HAS_PROVENANCE]->(p:_Provenance)-[:FROM_SOURCE]->(src)
RETURN n.id AS node_id, labels(src)[0] AS source_label, src.id AS source_id,
       coalesce(src.field_id, src.filename, '') AS source_ref,
       coalesce(src.value_json, src.summary, '') AS source_value, p.source AS source, p.confidence AS confidence
ORDER BY source_id
