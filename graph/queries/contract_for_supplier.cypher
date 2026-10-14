// name: contract_for_supplier
// purpose: The contract with a supplier and the document it lives in.
// kind: read
// params: {"sid": "SUP-T1-0001"}
MATCH (k:Contract {supplier_id: $sid})-[:WITH]->(s:Supplier)
OPTIONAL MATCH (k)-[:DOCUMENTED_IN]->(d:Document)
RETURN k.id AS contract_id, s.id AS supplier_id, s.name AS supplier, k.sla_days AS sla_days,
       k.penalty_pct AS penalty_pct, k.penalty_cap_pct AS penalty_cap_pct, k.force_majeure AS force_majeure,
       k.exclusivity AS exclusivity, k.start AS start, k.end AS end, d.id AS doc_id, d.title AS title, d.uri AS uri
