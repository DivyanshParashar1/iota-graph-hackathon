// name: load_contracts
// purpose: Ingest. Upsert contracts, Contract-[:WITH]->Supplier.
// kind: write
// params: {"rows": [{"id": "CON-TEST", "supplier_id": "SUP-TEST", "start": "2024-01-01", "end": "2027-12-31", "sla_days": 21, "penalty_pct": 1.0, "penalty_cap_pct": 10, "force_majeure": true, "exclusivity": false, "doc_id": "DOC-TEST"}]}
UNWIND $rows AS r
MERGE (k:Contract {id: r.id})
SET k.supplier_id = r.supplier_id, k.start = r.start, k.end = r.end, k.sla_days = r.sla_days,
    k.penalty_pct = r.penalty_pct, k.penalty_cap_pct = r.penalty_cap_pct, k.force_majeure = r.force_majeure,
    k.exclusivity = r.exclusivity, k.doc_id = r.doc_id
WITH k, r
MATCH (s:Supplier {id: r.supplier_id})
MERGE (k)-[:WITH]->(s)
