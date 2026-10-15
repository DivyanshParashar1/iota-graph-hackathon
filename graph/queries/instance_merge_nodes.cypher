// name: instance_merge_nodes
// purpose: Load instance rows as nodes of one generated type. Template: {label} comes from the approved spec.
// graph: ops
// kind: template
// params: {"rows": [{"id": "SUP-1", "name": "Acme"}]}
UNWIND $rows AS r
MERGE (n:{label} {{id: r.id}})
SET n += r
RETURN count(n) AS merged
