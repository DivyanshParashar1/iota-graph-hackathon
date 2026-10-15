import pytest

from ripple.db import TenantScope
from ripple.scenarios import scenario_event
from ripple.tools.memory import (conversations, facts_about, get_playbook, log_turn, recall_similar_episodes,
                                 record_episode, upsert_fact)
from ripple.tools.impact import blast_radius, trigger


@pytest.fixture(scope="module")
def scope(fresh_db):
    return TenantScope("dataco", fresh_db)


def test_seeded_memory(scope):
    pb = get_playbook(scope, disruption_type="port_closure").data["playbook"]
    assert pb["id"] == "PB-port-closure" and pb["success_rate"] == pytest.approx(5 / 6, abs=1e-3)
    n = scope.mem.query("MATCH (e:Episode) RETURN count(e) AS c")[0]["c"]
    assert n == 2
    nova = TenantScope("nova", scope.db)
    assert get_playbook(nova, disruption_type="port_closure").data["playbook"]["id"] == "PB-N-port-closure"


def test_recall_and_record_episode(scope):
    did, iid = trigger(scope, scenario_event("port_closure_shanghai", "dataco"))
    blast_radius(scope, disruption_id=did)
    r = recall_similar_episodes(scope, incident_id=iid)
    top = r.data["episodes"][0]
    assert top["disruption_type"] == "port_closure" and top["seeded"]
    assert top["score"] >= 0.5
    ep = record_episode(scope, incident_id=iid).data
    assert ep["created"] and ep["outcome"] == "failed"  # nothing was done
    assert ep["playbook"]["uses"] == 7 and ep["playbook"]["successes"] == 5
    again = record_episode(scope, incident_id=iid).data
    assert again["episode_id"] == ep["episode_id"] and not again["created"]
    assert get_playbook(scope, disruption_type="port_closure").data["playbook"]["uses"] == 7


def test_fact_contradiction_sets_invalid_at(scope):
    a = upsert_fact(scope, subject_id="SUP-T1-0001", predicate="reliability", object="high", source="test").data
    same = upsert_fact(scope, subject_id="SUP-T1-0001", predicate="reliability", object="high", source="test").data
    assert same["fact_id"] == a["fact_id"] and not same["created"]
    b = upsert_fact(scope, subject_id="SUP-T1-0001", predicate="reliability", object="degraded after strike",
                    source="test").data
    assert b["superseded"] == a["fact_id"]
    cur = facts_about(scope, subject_id="SUP-T1-0001").data["facts"]
    assert [f["object"] for f in cur] == ["degraded after strike"]
    hist = facts_about(scope, subject_id="SUP-T1-0001", include_history=True).data["facts"]
    old = next(f for f in hist if f["id"] == a["fact_id"])
    assert old["invalid_at"] is not None
    assert next(f for f in hist if f["id"] == b["fact_id"])["supersedes"] == a["fact_id"]


def test_conversation_log(scope):
    log_turn(scope, "USR-alice", "CONV-1", "user", "who owns Volt?")
    log_turn(scope, "USR-alice", "CONV-1", "assistant", "Priya", [{"doc_id": "DOC-CON-0001"}])
    conv = conversations(scope, "USR-alice")
    assert conv[0]["id"] == "CONV-1" and [m["role"] for m in conv[0]["messages"]] == ["user", "assistant"]
    assert conv[0]["messages"][1]["sources"][0]["doc_id"] == "DOC-CON-0001"


def test_restart_recall_reuses_playbook(db_copy_path):
    """Scenario A, close, restart (close the DB object, reopen the same file), scenario B recalls A."""
    from ripple.agents.orchestrator import Orchestrator
    from conftest import open_db

    from ripple.db import close_db
    from ripple.tools.actions import approve_action, execute_action, list_actions
    from ripple.tools.impact import get_incident
    from ripple.tools.memory import close_incident

    db = open_db(db_copy_path)
    s = TenantScope("dataco", db)
    iid_a = Orchestrator(s, "scripted").run(scenario_event("port_closure_shanghai", "dataco"))
    for a in list_actions(s, status="proposed", incident_id=iid_a):
        approve_action(s, action_id=a["id"], user="USR-judge")
        execute_action(s, action_id=a["id"])
    closed = close_incident(s, incident_id=iid_a).data
    assert closed["episode"]["outcome"] == "resolved"
    assert closed["episode"]["playbook_id"] == "PB-port-closure"
    assert closed["episode"]["playbook"]["uses"] == 7 and closed["episode"]["playbook"]["successes"] == 6
    ep_a = closed["episode"]["episode_id"]
    close_db(db)  # simulated restart: the embedded server stops, state is only in the .db file

    db2 = open_db(db_copy_path)
    s2 = TenantScope("dataco", db2)
    assert get_incident(s2, iid_a)["incident"]["status"] == "closed"
    iid_b = Orchestrator(s2, "scripted").run(scenario_event("port_congestion_ningbo", "dataco"))
    rec = get_incident(s2, iid_b)["incident"]
    assert rec["recalled_episodes"][0] == ep_a
    from ripple.agents.events import BUS

    msg = next(e for e in BUS.history(iid_b) if e["agent"] == "sentinel" and e["kind"] == "message")
    assert iid_a in msg["summary"]
    assert rec["playbook_id"] == "PB-port-closure"
    pb = get_playbook(s2, disruption_type="port_closure").data["playbook"]
    assert pb["uses"] == 7 and pb["successes"] == 6
    facts = facts_about(s2, subject_id="PORT-CNSHA").data["facts"]
    assert facts and iid_a in facts[0]["object"]
    close_db(db2)
