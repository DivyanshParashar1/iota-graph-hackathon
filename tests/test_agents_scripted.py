import time

import pytest

from ripple.agents.events import BUS
from ripple.agents.orchestrator import Orchestrator
from ripple.db import TenantScope
from ripple.scenarios import load_scenarios, scenario_event
from ripple.tools.actions import list_actions
from ripple.tools.impact import get_incident


@pytest.fixture(scope="module")
def scope(fresh_db):
    return TenantScope("dataco", fresh_db)


@pytest.mark.parametrize("sid", sorted(load_scenarios()))
def test_full_run(scope, sid):
    t0 = time.time()
    iid = Orchestrator(scope, "scripted").run(scenario_event(sid, "dataco"))
    wall = time.time() - t0
    assert wall < 60
    hs = scope.ops.run("incident_handoffs", {"iid": iid})
    pairs = [(h["src"], h["dst"]) for h in hs]
    assert set(pairs) == {("sentinel", "analyst"), ("sentinel", "comms"), ("analyst", "planner"),
                          ("comms", "planner"), ("planner", "comms")}
    assert {pairs[0], pairs[1]} == {("sentinel", "analyst"), ("sentinel", "comms")}
    assert pairs[-1] == ("planner", "comms")
    inc = get_incident(scope, iid)["incident"]
    assert inc["revenue_at_risk_initial"] > 0 and inc["orders_at_risk_initial"] >= 50
    assert inc["summary"] and inc["playbook_id"]
    acts = list_actions(scope, incident_id=iid)
    assert any(a["status"] == "executed" for a in acts)
    evs = BUS.history(iid)
    assert evs[-1]["kind"] == "done"
    assert [e["seq"] for e in evs] == list(range(1, len(evs) + 1))
    agents = {e["agent"] for e in evs}
    assert {"sentinel", "analyst", "planner", "comms"} <= agents
    assert any(e["kind"] == "tool_result" and e["tool"] == "blast_radius" and e["node_ids"] for e in evs)
    # the shared blackboard got every agent's tool calls
    calls = scope.ops.query("MATCH (:Incident {id: $iid})-[:HAS_CALL]->(t:ToolCall) RETURN DISTINCT t.agent AS a",
                            {"iid": iid})
    assert {"sentinel", "analyst", "planner", "comms"} <= {c["a"] for c in calls}


def test_rerun_is_idempotent(scope):
    ev = scenario_event("port_closure_shanghai", "dataco")
    iid = Orchestrator(scope, "scripted").run(ev)
    n_inc = scope.ops.query("MATCH (i:Incident {id: $iid}) RETURN count(i) AS c", {"iid": iid})[0]["c"]
    n_act = len(list_actions(scope, incident_id=iid))
    iid2 = Orchestrator(scope, "scripted").run(ev)
    assert iid2 == iid and n_inc == 1
    assert len(list_actions(scope, incident_id=iid)) == n_act
