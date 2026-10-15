// name: checklist_list
// purpose: A stage's checklist items (the agent's working memory; never rendered to the user)
// graph: ops
// kind: read
// params: {"stage": "interview"}
MATCH (c:_ChecklistItem)
WHERE c.stage = $stage
RETURN c.id AS id, c.stage AS stage, c.question AS question, c.why AS why, c.status AS status,
       c.answer_summary AS answer_summary, c.created_at AS created_at, c.resolved_at AS resolved_at
ORDER BY c.created_at
