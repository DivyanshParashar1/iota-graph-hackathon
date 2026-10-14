// name: claim_execution
// purpose: Write: atomically move an approved action to 'executing' so it can only run once.
// kind: write
// params: {"aid": "ACT-example"}
MATCH (a:Action {id: $aid})
WHERE a.status = 'approved'
SET a.status = 'executing'
RETURN a.id AS id, a.type AS type, a.params_json AS params
