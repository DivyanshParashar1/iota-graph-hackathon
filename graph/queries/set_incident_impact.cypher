// name: set_incident_impact
// purpose: Write: blast-radius numbers on the Incident blackboard (initial values kept for before/after).
// kind: write
// params: {"iid": "INC-example", "revenue": 0.0, "orders": 0, "customers": 0, "summary": "", "parts": []}
MATCH (i:Incident {id: $iid})
SET i.revenue_at_risk = $revenue, i.orders_at_risk = $orders, i.customers_affected = $customers,
    i.revenue_at_risk_initial = coalesce(i.revenue_at_risk_initial, $revenue),
    i.orders_at_risk_initial = coalesce(i.orders_at_risk_initial, $orders),
    i.impact_summary = $summary, i.parts_impacted = $parts
RETURN i.id AS id
