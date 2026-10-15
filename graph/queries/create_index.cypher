// name: create_index
// purpose: One index for a generated type. Template: {label}, {prop}; raises when the index already exists.
// graph: ops
// kind: template
// params: {}
CREATE INDEX FOR (n:{label}) ON (n.{prop})
