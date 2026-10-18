// name: single_linked_targets
// purpose: How many nodes of a type have exactly one partner over a many-to-many link (concentration risk). Template: {from_label}, {rel}, {to_label}.
// graph: ops
// kind: template
// params: {"limit": 5}
MATCH (b:{to_label})
OPTIONAL MATCH (a:{from_label})-[:{rel}]->(b)
WITH b, count(a) AS partners
RETURN sum(CASE WHEN partners = 1 THEN 1 ELSE 0 END) AS single, count(b) AS total,
       [x IN collect(CASE WHEN partners = 1 THEN b.id END) WHERE x IS NOT NULL][0..$limit] AS sample_ids
