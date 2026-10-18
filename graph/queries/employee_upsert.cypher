// name: employee_upsert
// purpose: Create or update an employee (a person who uses the workspace) and their assigned expert roles
// graph: ops
// kind: write
// params: {"row": {"id": "EMP-1", "name": "Maya Chen", "title": "Logistics lead", "roles_json": "[\"EXP-logistics\"]", "ts": 0}}
MERGE (e:_Employee {id: $row.id})
SET e += $row
RETURN e.id AS id
