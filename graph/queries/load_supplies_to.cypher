// name: load_supplies_to
// purpose: Ingest. Supplier-[:SUPPLIES_TO]->Supplier (tier3 -> tier2 -> tier1).
// kind: write
// params: {"rows": [{"src": "SUP-TEST", "dst": "SUP-TEST"}]}
UNWIND $rows AS r
MATCH (a:Supplier {id: r.src})
MATCH (b:Supplier {id: r.dst})
MERGE (a)-[:SUPPLIES_TO]->(b)
