// name: load_regions
// purpose: Ingest. Upsert DataCo markets and regions, Region-[:PART_OF]->Market.
// kind: write
// params: {"rows": [{"market_id": "MKT-Test", "market": "Test", "region_id": "REG-test", "region": "Test"}]}
UNWIND $rows AS r
MERGE (m:Market {id: r.market_id}) SET m.name = r.market
MERGE (g:Region {id: r.region_id}) SET g.name = r.region
MERGE (g)-[:PART_OF]->(m)
