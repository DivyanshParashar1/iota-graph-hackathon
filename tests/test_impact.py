"""blast_radius order ids and revenue exactly equal the pandas ground truth (eval/ground_truth.py)."""

import sys

import pytest

from ripple import ROOT
from ripple.db import TenantScope
from ripple.scenarios import load_scenarios, scenario_event
from ripple.tools.impact import blast_radius, customer_exposure, revenue_at_risk, trigger

sys.path.insert(0, str(ROOT / "eval"))
from ground_truth import ground_truth  # noqa: E402


@pytest.fixture(scope="module")
def scope(fresh_db):
    return TenantScope("dataco", fresh_db)


@pytest.mark.parametrize("sid", sorted(load_scenarios()))
def test_blast_radius_matches_ground_truth(scope, sid, sample_ids):
    gt = ground_truth(sid, "dataco", sample_ids)
    did, iid = trigger(scope, scenario_event(sid, "dataco"))
    br = blast_radius(scope, disruption_id=did)
    assert br.data["order_ids"] == gt["order_ids"]
    assert br.data["orders_at_risk"] == gt["orders"] >= 50
    assert br.data["revenue_at_risk"] == pytest.approx(gt["revenue"], abs=0.01)
    assert br.data["customers_affected"] == gt["customers"]
    assert br.node_ids and br.edges and len(br.node_ids) <= 201
    live = revenue_at_risk(scope, incident_id=iid)
    assert live.data["order_ids"] == gt["order_ids"]
    assert live.data["revenue_at_risk"] == pytest.approx(gt["revenue"], abs=0.01)
    ce = customer_exposure(scope, incident_id=iid, top_k=5)
    assert len(ce.data["top_customers"]) == 5
    assert sum(s["revenue"] for s in ce.data["segments"]) == pytest.approx(gt["revenue"], abs=0.05)


def test_tool_calls_are_logged(scope):
    n = scope.ops.query("MATCH (t:ToolCall {tool: 'blast_radius'}) RETURN count(t) AS c")[0]["c"]
    assert n >= 4
    linked = scope.ops.query("MATCH (:Incident)-[:HAS_CALL]->(t:ToolCall) RETURN count(t) AS c")[0]["c"]
    assert linked >= 4
