// name: incident_options_list
// purpose: Every option of one incident, by group and Jev's rank
// graph: ops
// kind: read
// params: {"iid": "INC-1"}
MATCH (:_Incident {id: $iid})-[:HAS_OPTION]->(o:_Option)
RETURN properties(o) AS props
ORDER BY o.group_id, o.rank, o.option_id
