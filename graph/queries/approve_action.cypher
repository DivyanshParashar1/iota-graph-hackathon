// name: approve_action
// purpose: Write: approve a proposed action; Action-[:APPROVED_BY]->User (governance).
// kind: write
// params: {"aid": "ACT-example", "uid": "USR-demo", "uname": "Demo user", "ts": 0}
MATCH (a:Action {id: $aid})
WHERE a.status = 'proposed'
MERGE (u:User {id: $uid})
ON CREATE SET u.name = $uname
MERGE (a)-[r:APPROVED_BY]->(u)
SET r.ts = $ts, a.status = 'approved', a.approved_at = $ts
RETURN a.id AS id, a.status AS status
