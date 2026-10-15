// name: checklist_upsert
// purpose: Create or update one internal checklist item of a stage agent
// graph: ops
// kind: write
// params: {"row": {"id": "CHK-1", "stage": "interview", "question": "?", "why": "", "status": "open", "answer_summary": "", "created_at": 0, "resolved_at": 0}}
MERGE (c:_ChecklistItem {id: $row.id})
SET c += $row
RETURN c.id AS id, c.status AS status
