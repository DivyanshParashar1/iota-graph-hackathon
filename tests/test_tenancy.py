import pytest

from ripple.db import TenantScope, TenantViolation
from ripple.scenarios import scenario_event
from ripple.tools.algos import single_points_of_failure
from ripple.tools.brain import ask
from ripple.tools.impact import blast_radius, trigger


def test_scope_cannot_open_other_tenant(built_db):
    s = TenantScope("dataco", built_db)
    with pytest.raises(TenantViolation):
        s.graph("tenant_nova")
    with pytest.raises(TenantViolation):
        s.graph("mem_nova")
    with pytest.raises(TenantViolation):
        TenantScope("acme", built_db)
    assert s.ops.name == "tenant_dataco" and s.mem.name == "mem_dataco"


def test_same_question_returns_disjoint_ids(fresh_db):
    d, n = TenantScope("dataco", fresh_db), TenantScope("nova", fresh_db)
    q = "Who on the team has handled a port closure before?"
    a, b = ask(d, question=q).data, ask(n, question=q).data
    assert a["path"] and b["path"] and not (set(a["path"]) & set(b["path"]))
    s1, s2 = single_points_of_failure(d, top_k=5), single_points_of_failure(n, top_k=5)
    assert not (set(s1.node_ids) & set(s2.node_ids))
    r = []
    for s in (d, n):
        did, iid = trigger(s, scenario_event("port_closure_shanghai", s.tenant_id))
        r.append(blast_radius(s, disruption_id=did))
    assert r[0].data["orders_at_risk"] > 0 and r[1].data["orders_at_risk"] > 0
    assert not (set(r[0].node_ids) & set(r[1].node_ids))
    assert all("-N-" in o for o in r[1].data["order_ids"])
    assert not any("-N-" in o for o in r[0].data["order_ids"])
