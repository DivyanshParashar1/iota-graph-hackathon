// name: employees_list
// purpose: Employees with team (author picker in the brain UI).
// kind: read
// params: {}
MATCH (e:Employee)
OPTIONAL MATCH (e)-[:MEMBER_OF]->(t:Team)
RETURN e.id AS id, e.name AS name, e.role AS role, t.name AS team
ORDER BY e.id
