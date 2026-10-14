// name: bump_risk
// purpose: Write: semantic memory feeds back into the ops graph: raise risk_score of entities hit by an incident.
// kind: write
// params: {"ids": ["PORT-CNSHA"], "delta": 0.1}
UNWIND $ids AS x
MATCH (n:RiskBearing {id: x})
SET n.risk_score = CASE WHEN n.risk_score + $delta > 1.0 THEN 1.0 ELSE round((n.risk_score + $delta) * 100) / 100.0 END
RETURN n.id AS id, n.risk_score AS risk_score
