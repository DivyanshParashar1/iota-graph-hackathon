// name: derived_from
// purpose: Record that an artifact was derived from the messages, answers and uploads listed
// graph: ops
// kind: write
// params: {"id": "BRF-1", "source_ids": ["MSG-1"]}
MATCH (a {id: $id})
MATCH (src)
WHERE src.id IN $source_ids
MERGE (a)-[:DERIVED_FROM]->(src)
RETURN count(src) AS links
