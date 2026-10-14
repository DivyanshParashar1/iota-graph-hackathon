// name: set_incident_context
// purpose: Write: Comms prefetch puts related suppliers and their owners on the Incident blackboard.
// kind: write
// params: {"iid": "INC-example", "suppliers": [], "owners": []}
MATCH (i:Incident {id: $iid})
SET i.related_suppliers = $suppliers, i.owner_ids = $owners
RETURN i.id AS id
