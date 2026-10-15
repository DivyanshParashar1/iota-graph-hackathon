// name: instance_merge_edges
// purpose: Load instance rows as edges of one generated relationship type. Template: {rel}, {from_label}, {to_label}.
// graph: ops
// kind: template
// params: {"rows": [{"from": "SUP-1", "to": "PRT-1", "props": {}}]}
UNWIND $rows AS r
MATCH (a:{from_label} {{id: r.from}})
MATCH (b:{to_label} {{id: r.to}})
MERGE (a)-[e:{rel}]->(b)
SET e += r.props
RETURN count(e) AS merged
