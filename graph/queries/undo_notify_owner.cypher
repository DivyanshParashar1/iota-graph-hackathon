// name: undo_notify_owner
// purpose: Undo NOTIFY_OWNER: mark the notification retracted.
// kind: write
// params: {"mid": "MSG-example"}
MATCH (m:ChatMessage {id: $mid})
SET m.sent = false, m.retracted = true
RETURN m.id AS id
