import json

from ripple.embed import get_embedder
from ripple.ingest.synth import SYNTH_DIR

PLANTED = json.loads((SYNTH_DIR / "dataco" / "planted.json").read_text())


def test_brain_ingest_counts(scope_dataco):
    q = scope_dataco.ops.query
    for label in ("Chunk", "Decision", "ChatMessage", "Document"):
        assert q(f"MATCH (n:{label}) RETURN count(n) AS c")[0]["c"] > 0
    assert q("MATCH ()-[r:MENTIONS]->() RETURN count(r) AS c")[0]["c"] > 0
    assert q("MATCH (:Decision)-[r:SOURCED_FROM]->() RETURN count(r) AS c")[0]["c"] > 0


def test_doc_search_battery_dual_source_finds_typhoon_postmortem(scope_dataco):
    qvec = get_embedder().embed("battery dual source")
    rows = scope_dataco.ops.run("doc_search", {"qvec": qvec, "k": 8, "scope": []})
    docs = []
    for r in rows:
        if r["doc_id"] not in docs:
            docs.append(r["doc_id"])
    assert PLANTED["hero"]["typhoon_postmortem"] in docs[:3], docs


DEMO = [
    ("Who owns our relationship with Shenzhen Volt Components, and who backs them up?", "owner",
     PLANTED["hero"]["contract_doc"]),
    ("Why did we dual-source the Li-ion battery pack?", "why", PLANTED["hero"]["typhoon_postmortem"]),
    ("What does the contract with Shenzhen Volt Components say about delay penalties, and are we owed anything for "
     "this incident?", "contract", PLANTED["hero"]["contract_doc"]),
    ("Who on the team has handled a port closure before?", "expertise", PLANTED["hero"]["port_closure_postmortems"][0]),
    ("What changed in our sourcing policy since the 2024 typhoon?", "change", PLANTED["hero"]["dual_sourcing_sop"]),
]


def test_demo_questions_cite_expected_sources(scope_dataco):
    from ripple.tools.brain import ask

    for q, intent, doc in DEMO:
        r = ask(scope_dataco, question=q).data
        assert intent in r["intent"], (q, r["intent"])
        assert doc in [s["doc_id"] for s in r["sources"]][:3], (q, r["sources"])
        assert r["path"] and r["answer"]
        for s in r["sources"]:
            assert {"doc_id", "title", "uri", "snippet"} <= set(s)
    owner = ask(scope_dataco, question=DEMO[0][0]).data
    assert PLANTED["hero"]["owner_id"] in owner["answer"]
    why = ask(scope_dataco, question=DEMO[1][0]).data
    assert "DOC-CHAT-001" in [s["doc_id"] for s in why["sources"]]  # decision -> postmortem -> chat thread


def test_contract_penalty_with_incident(fresh_db):
    from ripple.db import TenantScope
    from ripple.scenarios import scenario_event
    from ripple.tools.impact import blast_radius, trigger
    from ripple.tools.sourcing import contract_terms

    s = TenantScope("dataco", fresh_db)
    did, iid = trigger(s, {"type": "supplier_failure", "target_id": PLANTED["hero"]["supplier_id"],
                           "expected_days": 9, "name": "Volt plant fire"})
    blast_radius(s, disruption_id=did)
    c = contract_terms(s, supplier_id=PLANTED["hero"]["supplier_id"], incident_id=iid).data
    p = c["penalty"]
    assert p["exposed_orders"] > 0 and not p["force_majeure_applies"]  # a fire is not listed as force majeure
    assert p["owed"] == round(min(p["exposed_revenue"] * 0.015 * 9, p["exposed_revenue"] * 0.10), 2)
    _ = scenario_event


def test_handover_delta_changes_who_owns_and_conversation_is_stored(fresh_db):
    from ripple.db import TenantScope
    from ripple.ingest.delta import ingest_delta
    from ripple.tools.brain import ask, who_owns
    from ripple.tools.memory import conversations, facts_about

    s = TenantScope("dataco", fresh_db)
    hero = PLANTED["hero"]["supplier_id"]
    before = who_owns(s, entity_id=hero).data["owners"][0]["employee_id"]
    item = json.loads((SYNTH_DIR / "dataco" / "delta" / "handover.json").read_text())
    r = ingest_delta(s, kind="chat", text=item["text"], author_id=item["author_id"], channel=item["channel"]).data
    assert r["handover"]["supplier_id"] == hero
    assert r["handover"]["to"] == item["expected"]["new_owner_id"] != before
    after = who_owns(s, entity_id=hero).data["owners"][0]
    assert after["employee_id"] == item["expected"]["new_owner_id"]
    ans = ask(s, question="Who owns our relationship with Shenzhen Volt Components?", user_id="USR-judge").data
    assert item["expected"]["new_owner_id"] in ans["answer"]
    assert r["doc_id"] in [x["doc_id"] for x in ans["sources"]]  # the handover message is cited
    assert facts_about(s, subject_id=hero).data["facts"][0]["object"] == item["expected"]["new_owner_id"]
    conv = conversations(s, "USR-judge")
    assert conv and [m["role"] for m in conv[0]["messages"]][-2:] == ["user", "assistant"]
    # a document delta bumps the version
    d1 = ingest_delta(s, kind="doc", text="# Expedite Approval Matrix\n\nUp to $10,000: Transport Planner.",
                      doc_id="DOC-SOP-EXPEDITE-MATRIX").data
    assert d1["version"] == 2


def test_brain_eval_at_least_18_of_20(scope_dataco):
    import sys

    from ripple import ROOT

    sys.path.insert(0, str(ROOT / "eval"))
    from run_brain_eval import run

    res = run(scope_dataco, verbose=False)
    assert res["passed"] >= 18, [r for r in res["rows"] if not r["pass"]]
