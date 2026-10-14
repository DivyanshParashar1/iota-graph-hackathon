// name: alt_suppliers
// purpose: Q4. Qualified or active alternate suppliers for a part outside a blocked country, excluding suppliers hit by an active disruption directly or upstream (SUPPLIES_TO*1..2).
// kind: read
// params: {"part": "PRT-0001", "exclude_country": "CN", "limit": 5}
MATCH (pt:Part {id: $part})<-[q:QUALIFIED_FOR|SUPPLIES]-(s:Supplier)
WHERE ($exclude_country IS NULL OR s.country <> $exclude_country)
  AND NOT (s)<-[:AFFECTS]-(:Disruption {active: true})
  AND NOT (s)<-[:SUPPLIES_TO*1..2]-(:Supplier)<-[:AFFECTS]-(:Disruption {active: true})
RETURN s.id AS id, s.name AS name, s.country AS country, s.reliability AS reliability,
       coalesce(q.lead_time_days, 21) AS lead_time, q.unit_cost AS unit_cost, type(q) AS relation
ORDER BY CASE type(q) WHEN 'QUALIFIED_FOR' THEN 0 ELSE 1 END, reliability DESC, lead_time ASC
LIMIT $limit
