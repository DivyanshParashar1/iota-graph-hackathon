// name: exec_notify_owner
// purpose: Action effect NOTIFY_OWNER: post the notification as a ChatMessage to the owner; ChatMessage-[:NOTIFIES]->Employee, -[:ABOUT_ACTION]->Action.
// kind: write
// params: {"aid": "ACT-example", "mid": "MSG-example", "eid": "EMP-001", "text": "hello", "ts": "2026-10-15T09:00", "sent": true}
MATCH (a:Action {id: $aid})
MERGE (m:ChatMessage {id: $mid})
SET m.text = $text, m.ts = $ts, m.kind = 'notification', m.sent = $sent
MERGE (m)-[:ABOUT_ACTION]->(a)
WITH m
OPTIONAL MATCH (e:Employee {id: $eid})
FOREACH (_ IN CASE WHEN e IS NULL THEN [] ELSE [1] END | MERGE (m)-[:NOTIFIES]->(e))
RETURN m.id AS id
