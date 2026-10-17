// name: approvals_list
// purpose: Every approval and rejection on one incident, in order
// graph: ops
// kind: read
// params: {"iid": "INC-1"}
MATCH (:_Incident {id: $iid})-[:HAS_APPROVAL]->(a:_Approval)
RETURN properties(a) AS props
ORDER BY a.ns
