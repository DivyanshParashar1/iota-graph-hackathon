import pytest

from ripple.ingest.dataco import OPEN_STATUSES, order_frame, read_raw

PII = {"email", "fname", "lname", "password", "street", "zipcode", "customer email", "customer fname",
       "customer lname", "customer password", "customer street", "customer zipcode", "latitude", "longitude"}


def _expected(sample_ids):
    raw = read_raw()
    raw = raw[raw["Order Id"].isin(set(sample_ids))]
    o = order_frame(raw)
    return raw, o


def test_counts_match_pandas(scope_dataco, sample_ids):
    raw, o = _expected(sample_ids)
    q = scope_dataco.ops.query
    assert q("MATCH (o:Order) RETURN count(o) AS c")[0]["c"] == len(o) == len(sample_ids)
    assert q("MATCH (l:OrderLine) RETURN count(l) AS c")[0]["c"] == len(raw)
    assert q("MATCH (c:Customer) RETURN count(c) AS c")[0]["c"] == raw["Order Customer Id"].nunique()
    assert q("MATCH (p:Product) RETURN count(p) AS c")[0]["c"] == 118
    assert q("MATCH (o:Order {open: true}) RETURN count(o) AS c")[0]["c"] == int(o["status"].isin(OPEN_STATUSES).sum())
    tot = q("MATCH (o:Order) RETURN sum(o.total) AS s")[0]["s"]
    assert tot == pytest.approx(float(o["total"].sum()), abs=0.01)
    # one order spot check
    r = o.iloc[0]
    row = q("MATCH (o:Order {id: $id})-[:PLACED_BY]->(c:Customer) RETURN o.total AS t, o.status AS s, c.id AS c",
            {"id": f"ORD-{r['Order Id']}"})[0]
    assert row == {"t": float(r["total"]), "s": r["status"], "c": f"CUS-{r['customer']}"}


def test_no_pii_property_keys(scope_dataco):
    keys = {r["k"].lower() for r in scope_dataco.ops.query("CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey AS k")}
    assert not (keys & PII), keys & PII


def test_every_order_has_one_lane(scope_dataco, scope_nova):
    for s in (scope_dataco, scope_nova):
        rows = s.ops.query("MATCH (o:Order) OPTIONAL MATCH (o)-[r:SHIPS_VIA]->(:Lane) WITH o, count(r) AS n "
                           "RETURN n, count(o) AS c")
        assert rows == [{"n": 1, "c": rows[0]["c"]}]


@pytest.mark.slow
def test_full_build_counts(full_db):
    from ripple.db import TenantScope

    s = TenantScope("dataco", full_db)
    q = s.ops.query
    assert q("MATCH (o:Order) RETURN count(o) AS c")[0]["c"] == 65752
    assert q("MATCH (l:OrderLine) RETURN count(l) AS c")[0]["c"] == 180519
    assert q("MATCH (c:Customer) RETURN count(c) AS c")[0]["c"] == 20652
    assert q("MATCH (o:Order {open: true}) RETURN count(o) AS c")[0]["c"] == 33932
    rows = q("MATCH (o:Order) OPTIONAL MATCH (o)-[r:SHIPS_VIA]->(:Lane) WITH o, count(r) AS n RETURN n, count(o) AS c")
    assert rows == [{"n": 1, "c": 65752}]
