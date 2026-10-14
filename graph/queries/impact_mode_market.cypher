// name: impact_mode_market
// purpose: The (shipping mode, market) pairs carrying most revenue in an impact set.
// kind: read
// params: {"order_ids": ["ORD-77202"]}
UNWIND $order_ids AS oid
MATCH (o:Order {id: oid})
RETURN o.shipping_mode AS mode, o.market AS market, count(o) AS orders, sum(o.total) AS revenue
ORDER BY revenue DESC LIMIT 3
