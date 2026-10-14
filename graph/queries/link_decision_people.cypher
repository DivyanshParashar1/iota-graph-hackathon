// name: link_decision_people
// purpose: Ingest. Employee-[:PARTICIPATED_IN]->Decision.
// kind: write
// params: {"rows": [{"decision_id": "DEC-TEST", "employee_id": "EMP-TEST"}]}
UNWIND $rows AS r
MATCH (d:Decision {id: r.decision_id})
MATCH (e:Employee {id: r.employee_id})
MERGE (e)-[:PARTICIPATED_IN]->(d)
