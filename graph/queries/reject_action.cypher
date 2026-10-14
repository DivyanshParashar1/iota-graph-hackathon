// name: reject_action
// purpose: Write: reject a proposed action; Action-[:REJECTED_BY]->User.
// kind: write
// params: {"aid": "ACT-example", "uid": "USR-demo", "uname": "Demo user", "ts": 0, "reason": ""}
MATCH (a:Action {id: $aid})
WHERE a.status = 'proposed'
MERGE (u:User {id: $uid})
ON CREATE SET u.name = $uname
MERGE (a)-[r:REJECTED_BY]->(u)
SET r.ts = $ts, a.status = 'rejected', a.rejected_at = $ts, a.reject_reason = $reason
RETURN a.id AS id, a.status AS status
