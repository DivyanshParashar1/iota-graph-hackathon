// name: incidents_list
// purpose: All incidents, newest first, with their numbers.
// kind: read
// params: {"limit": 100}
MATCH (i:Incident)
RETURN i.id AS id, i.title AS title, i.type AS type, i.status AS status, i.opened_at AS opened_at,
       i.closed_at AS closed_at, i.revenue_at_risk AS revenue_at_risk, i.revenue_at_risk_initial AS revenue_at_risk_initial,
       i.orders_at_risk AS orders_at_risk, i.customers_affected AS customers_affected, i.mode AS mode,
       i.outcome AS outcome
ORDER BY i.opened_at DESC LIMIT $limit
