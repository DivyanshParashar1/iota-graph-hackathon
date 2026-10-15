// name: doc_version
// purpose: Delta ingest: current version of a document (to bump it on re-ingest).
// kind: read
// params: {"id": "DOC-SOP-DUAL-SOURCING"}
MATCH (d:Document {id: $id})
RETURN d.version AS version
