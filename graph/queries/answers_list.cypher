// name: answers_list
// purpose: Every answer of the data pack (optionally one form round)
// graph: ops
// kind: read
// params: {"form_id": ""}
MATCH (a:_FormAnswer)
WHERE $form_id = '' OR a.form_id = $form_id
RETURN a.id AS id, a.form_id AS form_id, a.field_id AS field_id, a.value_json AS value_json,
       a.source AS source, a.confidence AS confidence, a.ts AS ts
ORDER BY a.ts
