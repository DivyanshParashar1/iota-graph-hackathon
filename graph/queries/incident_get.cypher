// name: incident_get
// purpose: One incident with every stored property (the JSON artifacts are decoded in ripple/incident/store.py)
// graph: ops
// kind: read
// params: {"id": "INC-1"}
MATCH (i:_Incident {id: $id})
RETURN properties(i) AS props
