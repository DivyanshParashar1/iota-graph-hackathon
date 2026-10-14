// name: match_supplier_by_name
// purpose: Event matching: suppliers whose name (or id) matches the event's target.
// kind: read
// params: {"name": "Shenzhen Volt"}
MATCH (s:Supplier)
WHERE toLower(s.name) CONTAINS toLower($name) OR s.id = $name
RETURN s.id AS id, 'Supplier' AS label, s.name AS name, s.country AS country, s.lat AS lat, s.lon AS lon, s.tier AS tier
