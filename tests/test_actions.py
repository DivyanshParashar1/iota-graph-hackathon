import pytest

from ripple.agents.planning import plan_alt_suppliers, plan_reroute
from ripple.db import TenantScope
from ripple.scenarios import scenario_event
from ripple.tools.actions import (approve_action, draft_notification, execute_action, get_action, list_actions,
                                  propose_action, reject_action, undo_action)
from ripple.tools.base import ToolError
from ripple.tools.impact import blast_radius, revenue_at_risk, trigger


@pytest.fixture(scope="module")
def scope(fresh_db):
    return TenantScope("dataco", fresh_db)


@pytest.fixture(scope="module")
def shanghai(scope):
    did, iid = trigger(scope, scenario_event("port_closure_shanghai", "dataco"))
    blast_radius(scope, disruption_id=did)
    return iid


def test_reroute_lifecycle_lowers_revenue_and_undo_restores(scope, shanghai):
    iid = shanghai
    r0 = revenue_at_risk(scope, incident_id=iid).data["revenue_at_risk"]
    plan = plan_reroute(scope, iid)
    assert plan and plan["orders"] > 0
    p = propose_action(scope, incident_id=iid, type="REROUTE_ORDERS", params=plan["params"],
                       evidence_ids=plan["evidence"], agent="planner", summary=plan["summary"])
    aid = p.data["action_id"]
    assert p.data["status"] == "proposed" and not p.data["auto_approvable"]
    # duplicate propose -> same id, no duplicate node
    p2 = propose_action(scope, incident_id=iid, type="REROUTE_ORDERS", params=plan["params"],
                        evidence_ids=plan["evidence"], agent="planner", summary=plan["summary"])
    assert p2.data["action_id"] == aid
    assert scope.ops.query("MATCH (a:Action {id: $id}) RETURN count(a) AS c", {"id": aid})[0]["c"] == 1
    # evidence is BASED_ON-linked
    a = get_action(scope, aid)
    assert {e["id"] for e in a["evidence"]} == set(plan["evidence"])
    # needs approval
    with pytest.raises(ToolError):
        execute_action(scope, action_id=aid)
    approve_action(scope, action_id=aid, user="USR-test")
    ex = execute_action(scope, action_id=aid)
    assert ex.data["revenue_before"] == pytest.approx(r0, abs=0.01)
    assert ex.data["revenue_after"] < r0
    assert ex.data["revenue_after"] == pytest.approx(0.0, abs=0.01)  # every impacted order moved off Shanghai
    # executing twice is a no-op
    ex2 = execute_action(scope, action_id=aid)
    assert ex2.data["noop"] is True
    assert revenue_at_risk(scope, incident_id=iid).data["revenue_at_risk"] == pytest.approx(0.0, abs=0.01)
    assert get_action(scope, aid)["approved_by"] == "USR-test"
    # undo restores
    u = undo_action(scope, action_id=aid)
    assert u.data["revenue_after"] == pytest.approx(r0, abs=0.01)
    assert get_action(scope, aid)["status"] == "undone"
    assert scope.ops.query("MATCH (:Action)-[:REVERSES]->(a:Action {id: $id}) RETURN count(a) AS c",
                           {"id": aid})[0]["c"] == 1
    every = scope.ops.query("MATCH (o:Order) OPTIONAL MATCH (o)-[r:SHIPS_VIA]->() WITH o, count(r) AS n "
                            "WHERE n <> 1 RETURN count(o) AS c")[0]["c"]
    assert every == 0


def test_notify_and_hold_auto_execute(scope, shanghai):
    p = propose_action(scope, incident_id=shanghai, type="NOTIFY_OWNER",
                       params={"employee_id": "EMP-011", "text": "Shanghai is closed"}, evidence_ids=["PORT-CNSHA"])
    assert p.data["auto_approvable"]
    ex = execute_action(scope, action_id=p.data["action_id"])
    assert ex.data["status"] == "executed"
    assert get_action(scope, p.data["action_id"])["approved_by"] == "USR-policy"
    d = draft_notification(scope, action_id=p.data["action_id"])
    assert d.data["to"] == "EMP-011" and "INC-" in d.data["text"]


def test_reject(scope, shanghai):
    p = propose_action(scope, incident_id=shanghai, type="EXPEDITE",
                       params={"order_ids": revenue_at_risk(scope, incident_id=shanghai).data["order_ids"][:3]},
                       evidence_ids=["PORT-CNSHA"])
    r = reject_action(scope, action_id=p.data["action_id"], reason="too expensive")
    assert r.data["status"] == "rejected"
    assert execute_action(scope, action_id=p.data["action_id"]).data["noop"]
    assert any(a["id"] == p.data["action_id"] for a in list_actions(scope, status="rejected"))


def test_unknown_evidence_rejected(scope, shanghai):
    with pytest.raises(ToolError):
        propose_action(scope, incident_id=shanghai, type="PLACE_HOLD", params={"order_ids": []},
                       evidence_ids=["SUP-DOES-NOT-EXIST"])


def test_alt_supplier_activation_lowers_revenue(scope):
    did, iid = trigger(scope, scenario_event("tier2_fire", "dataco"))
    br = blast_radius(scope, disruption_id=did)
    r0 = br.data["revenue_at_risk"]
    plan = plan_alt_suppliers(scope, iid, br.data["parts_impacted"])
    assert plan
    p = propose_action(scope, incident_id=iid, type="ACTIVATE_ALT_SUPPLIER", params=plan["params"],
                       evidence_ids=plan["evidence"], summary=plan["summary"])
    approve_action(scope, action_id=p.data["action_id"])
    ex = execute_action(scope, action_id=p.data["action_id"])
    assert ex.data["revenue_after"] < r0
    u = undo_action(scope, action_id=p.data["action_id"])
    assert u.data["revenue_after"] == pytest.approx(r0, abs=0.01)


def test_carrier_strike_reroute(scope):
    did, iid = trigger(scope, scenario_event("carrier_strike", "dataco"))
    r0 = blast_radius(scope, disruption_id=did).data["revenue_at_risk"]
    plan = plan_reroute(scope, iid)
    p = propose_action(scope, incident_id=iid, type="REROUTE_ORDERS", params=plan["params"], evidence_ids=plan["evidence"])
    approve_action(scope, action_id=p.data["action_id"])
    ex = execute_action(scope, action_id=p.data["action_id"])
    assert ex.data["revenue_after"] < r0
    undo_action(scope, action_id=p.data["action_id"])
