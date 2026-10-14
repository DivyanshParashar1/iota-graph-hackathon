// name: set_incident_live
// purpose: Write: refresh the live revenue/orders at risk on the Incident.
// kind: write
// params: {"iid": "INC-example", "revenue": 0.0, "orders": 0}
MATCH (i:Incident {id: $iid})
SET i.revenue_at_risk = $revenue, i.orders_at_risk = $orders
RETURN i.id AS id
