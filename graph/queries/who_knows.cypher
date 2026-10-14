// name: who_knows
// purpose: Expertise ranking: employees who AUTHORED documents, POSTED messages or PARTICIPATED_IN decisions that MENTION / are ABOUT the given entities (weights 2/1/3).
// kind: read
// params: {"ids": ["SUP-T1-0001"], "k": 5}
CALL {
  MATCH (ch:Chunk)-[:MENTIONS]->(ent)
  WHERE ent.id IN $ids
  MATCH (d:Document)-[:HAS_CHUNK]->(ch)
  MATCH (e:Employee)-[:AUTHORED]->(d)
  RETURN DISTINCT e, d.id AS src, 2 AS w
  UNION ALL
  MATCH (m:ChatMessage)-[:MENTIONS]->(ent)
  WHERE ent.id IN $ids
  MATCH (e:Employee)-[:POSTED]->(m)
  MATCH (th:Thread)-[:HAS_MSG]->(m)
  MATCH (th)-[:THREAD_DOC]->(d:Document)
  RETURN DISTINCT e, d.id AS src, 1 AS w
  UNION ALL
  MATCH (dec:Decision)-[:ABOUT]->(ent)
  WHERE ent.id IN $ids
  MATCH (e:Employee)-[:PARTICIPATED_IN]->(dec)
  RETURN DISTINCT e, dec.id AS src, 3 AS w
}
WITH e, sum(w) AS score, collect(DISTINCT src) AS sources
OPTIONAL MATCH (e)-[:MEMBER_OF]->(t:Team)
RETURN e.id AS employee_id, e.name AS name, e.role AS role, t.name AS team, score, sources
ORDER BY score DESC, employee_id LIMIT $k
