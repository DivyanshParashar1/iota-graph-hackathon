// name: employees_list
// purpose: Every employee, by name
// graph: ops
// kind: read
// params: {}
MATCH (e:_Employee)
RETURN e.id AS id, e.name AS name, e.title AS title, e.roles_json AS roles_json, e.ts AS ts
ORDER BY e.name
