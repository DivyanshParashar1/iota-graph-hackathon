"""The onboarding store: write, read, resume, versioning, staleness."""

from __future__ import annotations

import pytest

from ripple.db import TenantScope, TenantViolation, slug_tenant_id, valid_tenant_id
from ripple.onboarding import store
from ripple.onboarding.models import ChecklistOp, Message
from tests import factories as f


def test_tenant_ids():
    assert valid_tenant_id("acme_1a2b3c")
    assert not valid_tenant_id("Acme")
    assert not valid_tenant_id("1acme")
    assert not valid_tenant_id("acme-1")
    assert not valid_tenant_id("")
    tid = slug_tenant_id("Açmé Shoes & Co.")
    assert valid_tenant_id(tid) and tid.startswith("acme_shoes_co_")
    assert slug_tenant_id("") != slug_tenant_id("")  # unique even with no name


def test_tenant_scope_is_the_isolation_boundary(db):
    s = TenantScope("acme_test", db)
    assert s.ops.name == "tenant_acme_test"
    assert s.mem.name == "mem_acme_test"
    with pytest.raises(TenantViolation):
        s.graph("tenant_other")
    with pytest.raises(TenantViolation):
        TenantScope("../etc", db)


def test_tenant_and_session(scope):
    t = store.get_tenant(scope)
    assert t["name"] == "Acme Shoes" and t["stage"] == "interview" and t["status"] == "onboarding"
    sess = store.create_session(scope, "stub", "stub-1")
    assert store.get_session(scope)["id"] == sess["id"]
    store.set_session(scope, sess["id"], stage="data")
    assert store.get_session(scope)["stage"] == "data"
    store.set_tenant(scope, has_synthetic=True)
    assert store.get_tenant(scope)["has_synthetic"] is True


def test_messages_are_ordered_and_resumable(scope):
    sess = store.create_session(scope, "stub", "stub-1")
    sid = sess["id"]
    for i in range(5):
        store.append_message(scope, sid, Message(role="user", text=f"m{i}"))
    msgs = store.list_messages(scope, sid)
    assert [m.text for m in msgs] == ["m0", "m1", "m2", "m3", "m4"]
    assert [m.seq for m in msgs] == [1, 2, 3, 4, 5]
    assert [m.text for m in store.list_messages(scope, sid, after=3)] == ["m3", "m4"]
    store.append_message(scope, sid, Message(role="agent", agent="interviewer", kind="form", text="fill this",
                                             payload={"id": "FRM-001", "fields": [1, 2]}))
    assert store.list_messages(scope, sid)[-1].payload["id"] == "FRM-001"


def test_pending_turn_survives_a_restart(scope, db, tmp_path):
    sess = store.create_session(scope, "stub", "stub-1")
    store.set_pending(scope, sess["id"], {"stage": "interview", "user_text": "we make shoes"})
    reopened = TenantScope(scope.tenant_id, db)
    assert store.get_pending(reopened)["user_text"] == "we make shoes"
    store.set_pending(scope, sess["id"], None)
    assert store.get_pending(reopened) is None


def test_checklist_ops(scope):
    items = store.apply_checklist_ops(scope, "interview", [
        ChecklistOp(op="add", id="CHK-1", question="how many suppliers?", why="sizing"),
        ChecklistOp(op="add", id="CHK-2", question="which ports?", why="routing"),
    ])
    assert {i.id for i in items} == {"CHK-1", "CHK-2"}
    assert len(store.open_checklist(scope, "interview")) == 2
    store.apply_checklist_ops(scope, "interview", [
        ChecklistOp(op="resolve", id="CHK-1", answer_summary="about 40"),
        ChecklistOp(op="drop", id="CHK-2", answer_summary="they do not ship by sea"),
    ])
    by_id = {i.id: i for i in store.list_checklist(scope, "interview")}
    assert by_id["CHK-1"].status == "resolved" and by_id["CHK-1"].answer_summary == "about 40"
    assert by_id["CHK-2"].status == "dropped"
    assert store.open_checklist(scope, "interview") == []
    # a stage only sees its own checklist
    store.apply_checklist_ops(scope, "data", [ChecklistOp(op="add", id="CHK-9", question="unit costs?")])
    assert [i.id for i in store.list_checklist(scope, "data")] == ["CHK-9"]


def test_brief_versions_and_merge(scope):
    b = f.brief()
    row = store.put_brief(scope, b)
    assert (row["version"], row["id"]) == (1, "BRF-001")
    # patched in place while the version is open
    b2 = b.merge({"risks": ["carrier strikes"], "company": "Acme Shoes GmbH"})
    assert store.put_brief(scope, b2)["version"] == 1
    loaded, _ = store.current_brief(scope)
    assert loaded.company == "Acme Shoes GmbH"
    assert set(loaded.risks) == {"single-sourced soles", "carrier strikes"}
    # approving closes the version; the next write cuts a new one
    store.put_brief(scope, b2, approved=True)
    assert store.put_brief(scope, b2.merge({"markets": ["US"]}))["version"] == 2
    assert [r["version"] for r in store.brief_versions(scope)] == [2, 1]


def test_brief_merge_rules():
    b = f.brief()
    merged = b.merge({"products": [{"name": "Runner"}, {"name": "Trail"}], "vocabulary": {"DC": "warehouse"},
                      "summary": "", "industry": "sportswear"})
    assert [p.name for p in merged.products] == ["Runner", "Trail"]  # no duplicate Runner
    assert merged.vocabulary == {"SKU-R": "the Runner line", "DC": "warehouse"}
    assert merged.summary == b.summary  # an empty value never overwrites
    assert merged.industry == "sportswear"
    assert b.merge(None).model_dump() == b.model_dump()


def test_core_gaps():
    from ripple.onboarding.models import Brief

    assert "company" in Brief().core_gaps()
    assert f.brief().core_gaps() == []
    assert "the pain that brought them here" in f.brief(pains=[]).core_gaps()


def test_forms_and_answers(scope):
    form = store.save_form(scope, f.form())
    assert form.id == "FRM-001" and form.round == 1
    assert store.open_form(scope).id == form.id
    second = store.save_form(scope, f.form(title="Round 2"))
    assert (second.id, second.round) == ("FRM-002", 2)
    from ripple.onboarding.agents.data_agent import save_values

    save_values(scope, form, {"supplier_count": "40", "uses_air": "yes",
                              "tier1": [{"name": "GZ Leather", "lead_time_days": 30}]})
    answers = {a.field_id: a.value for a in store.list_answers(scope, form.id)}
    assert answers["supplier_count"] == 40 and answers["uses_air"] is True
    assert answers["tier1"][0]["name"] == "GZ Leather"
    # re-saving a field overwrites it rather than adding a second answer
    save_values(scope, form, {"supplier_count": 41})
    assert len(store.list_answers(scope, form.id)) == 3
    assert {a.field_id: a.value for a in store.list_answers(scope, form.id)}["supplier_count"] == 41
    store.set_form_status(scope, form.id, "submitted")
    assert store.open_form(scope).id == second.id


def test_spec_versions_and_approval(scope):
    row = store.save_spec(scope, f.spec(), status="draft")
    assert row["version"] == 1
    spec, _got = store.current_spec(scope)
    assert [t.label for t in spec.types] == ["Supplier", "Part", "Product"]
    assert spec.relationships[0].from_ == "Supplier"  # the `from` alias round-trips
    assert store.approved_spec(scope) == (None, None)
    store.set_spec_status(scope, row["id"], "approved")
    approved, _ = store.approved_spec(scope)
    assert approved.version == 1
    v2 = store.save_spec(scope, f.spec(rationale="v2"), status="draft", new_version=True)
    assert v2["version"] == 2
    store.set_spec_status(scope, v2["id"], "approved")
    assert store.approved_spec(scope)[1]["version"] == 2
    statuses = {r["version"]: r["status"] for r in store.spec_versions(scope)}
    assert statuses == {1: "superseded", 2: "approved"}
    types = scope.ops.run("ontology_types_list", {"oid": v2["id"]})
    assert [x["label"] for x in types if x["kind"] == "node"] == ["Part", "Product", "Supplier"]


def test_experts_crud(scope):
    saved = store.save_expert(scope, f.role())
    assert saved.id == "EXP-sourcing_risk"
    got = store.get_expert(scope, saved.id)
    assert got.focus_types == ["Supplier", "Part"] and got.tools[0] == "describe_ontology"
    assert got.playbook and got.status == "draft"
    store.set_expert_status(scope, saved.id, "approved")
    assert store.get_expert(scope, saved.id).status == "approved"
    store.save_expert(scope, f.role(name="customs", justification="Part and Product customs classification"))
    assert {e.name for e in store.list_experts(scope)} == {"sourcing_risk", "customs"}
    store.delete_expert(scope, "EXP-customs")
    assert [e.name for e in store.list_experts(scope)] == ["sourcing_risk"]
    assert store.get_expert(scope, "EXP-customs") is None


def test_staleness_marks_downstream_artifacts(scope):
    store.put_brief(scope, f.brief())
    row = store.save_spec(scope, f.spec(), status="draft")
    store.save_expert(scope, f.role())
    assert store.mark_stale(scope, ["_OntologySpec", "_ExpertRole"]) == 2
    assert store.current_spec(scope)[1]["stale"] is True
    assert store.list_experts(scope)[0].stale is True
    assert store.current_brief(scope)[1]["stale"] is False  # upstream is untouched
    # approving a role clears its staleness
    store.set_expert_status(scope, "EXP-sourcing_risk", "approved")
    assert store.list_experts(scope)[0].stale is False
    assert row["id"] == "ONT-001"


def test_steps_are_recorded(scope):
    from ripple.onboarding.models import AgentStep

    store.record_step(scope, AgentStep(stage="interview", agent="interviewer", kind="llm", summary="thinking",
                                       payload={"turns": 3}, ms=12.5))
    store.record_step(scope, AgentStep(stage="data", agent="data_agent", kind="write", summary="form saved"))
    assert len(store.list_steps(scope)) == 2
    one = store.list_steps(scope, "interview")
    assert len(one) == 1 and one[0]["payload"] == {"turns": 3} and one[0]["ms"] == 12.5
