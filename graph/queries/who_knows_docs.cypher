// name: who_knows_docs
// purpose: Expertise for a topic: authors of, posters in, and decision participants from the documents a doc_search found (postmortems weigh 3, chats 2, others 1).
// kind: read
// params: {"docs": ["DOC-PM-2024-SZX-TYPHOON"], "k": 5}
UNWIND $docs AS did
MATCH (d:Document {id: did})
CALL {
  WITH d
  MATCH (e:Employee)-[:AUTHORED]->(d)
  RETURN e, 'authored' AS how
  UNION
  WITH d
  MATCH (:Decision)-[:SOURCED_FROM]->(d)
  MATCH (e:Employee)-[:PARTICIPATED_IN]->(:Decision)-[:SOURCED_FROM]->(d)
  RETURN e, 'decided' AS how
}
WITH e, d, how, CASE d.type WHEN 'postmortem' THEN 3 WHEN 'chat_thread' THEN 2 ELSE 1 END AS w
WITH e, sum(w) AS score, collect(DISTINCT d.id) AS sources, collect(DISTINCT how) AS how
OPTIONAL MATCH (e)-[:MEMBER_OF]->(t:Team)
RETURN e.id AS employee_id, e.name AS name, e.role AS role, t.name AS team, score, sources, how
ORDER BY score DESC, employee_id LIMIT $k
