// name: decisions_all
// purpose: Every decision with what it is ABOUT (for keyword matching of 'why' and 'what changed' questions).
// kind: read
// params: {}
MATCH (dec:Decision)
OPTIONAL MATCH (dec)-[:ABOUT]->(x)
RETURN dec.id AS id, dec.summary AS summary, dec.decided_at AS decided_at, dec.status AS status,
       collect(DISTINCT x.id) AS about, collect(DISTINCT x.name) AS about_names
ORDER BY decided_at DESC
