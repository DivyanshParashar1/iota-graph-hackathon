// name: answer_upsert
// purpose: Save one form answer (per-field autosave); re-saving a field overwrites it
// graph: ops
// kind: write
// params: {"row": {"id": "ANS-1", "form_id": "FRM-1", "field_id": "f1", "value_json": "1", "source": "user", "confidence": "exact", "ts": 0}}
MERGE (a:_FormAnswer {id: $row.id})
SET a += $row
WITH a
MATCH (f:_FormSpec {id: a.form_id})
MERGE (f)-[:HAS_ANSWER]->(a)
RETURN a.id AS id, a.field_id AS field_id
