// name: incident_concerns_link
// purpose: Link an incident to the instance nodes its evidence names (unlabelled match: incidents name few ids)
// graph: ops
// kind: write
// params: {"iid": "INC-1", "ids": ["SUP-0001"]}
MATCH (i:_Incident {id: $iid})
MATCH (n)
WHERE n.id IN $ids AND NOT any(l IN labels(n) WHERE l STARTS WITH '_')
MERGE (i)-[:CONCERNS]->(n)
RETURN count(n) AS linked
