// name: jev_decisions_list
// purpose: Every Jev call of one incident, in order
// graph: ops
// kind: read
// params: {"iid": "INC-1"}
MATCH (:_Incident {id: $iid})-[:DECIDED_BY]->(d:_JevDecision)
RETURN properties(d) AS props
ORDER BY d.ns
