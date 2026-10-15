// name: provenance_wipe
// purpose: Delete provenance nodes whose instance node is gone (after an instance wipe)
// graph: ops
// kind: write
// params: {}
MATCH (p:_Provenance)
WHERE NOT (p)<-[:HAS_PROVENANCE]-()
DETACH DELETE p
RETURN count(p) AS deleted
