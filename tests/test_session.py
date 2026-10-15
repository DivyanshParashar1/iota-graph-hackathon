"""The stage machine: turns, the core-topic guard, advancing, resume, jumping back and staleness.

The agents run for real here - what is stubbed is the transport underneath them, so the code path is the one
production takes, with the model's reply supplied by the test instead of by a model.
"""

from __future__ import annotations

import pytest

from ripple.onboarding import session as sess
from ripple.onboarding import store
from ripple.onboarding.models import Message
from tests import factories as f


def interview_turn(**over) -> dict:
    data = {"reply": "Tell me about your products.", "checklist_ops": [], "brief_patch": {},
            "ask_for_files": [], "done": False, "done_reason": ""}
    data.update(over)
    return data


def data_turn(**over) -> dict:
    data = {"reply": "A few numbers, please.", "form": f.form().model_dump(), "checklist_ops": [],
            "ask_for_files": [], "file_mappings": [], "done": False, "done_reason": ""}
    data.update(over)
    return data


def ontology_turn(**over) -> dict:
    data = {"reply": "Here is the model.", "spec": f.spec().model_dump(by_alias=True), "questions": []}
    data.update(over)
    return data


def experts_turn(**over) -> dict:
    data = {"reply": "Four roles.", "roles": [f.role().model_dump()], "dropped": []}
    data.update(over)
    return data


@pytest.fixture
def started(db, stub, request):
    """A tenant whose onboarding has started (the interviewer's opening turn has run)."""
    from tests.conftest import tenant_id_for

    stub.load(interview_turn(checklist_ops=[{"op": "add", "id": "CHK-1", "question": "products?",
                                             "why": "core"}],
                             brief_patch={"company": "Acme Shoes"}))
    tid = tenant_id_for(request.node.name)
    from ripple.db import TenantScope

    TenantScope(tid, db).drop()
    scope = sess.start(db, "Acme Shoes", "footwear", tenant_id=tid)
    yield scope
    scope.drop()


def test_start_creates_everything_and_runs_the_opening_turn(started, stub):
    scope = started
    assert store.get_tenant(scope)["name"] == "Acme Shoes"
    sid = store.get_session(scope)["id"]
    msgs = store.list_messages(scope, sid)
    assert [m.role for m in msgs] == ["agent"]
    assert msgs[0].agent == "interviewer" and "products" in msgs[0].text
    assert [c.question for c in store.open_checklist(scope, "interview")] == ["products?"]
    assert store.current_brief(scope)[0].company == "Acme Shoes"
    assert len(stub.calls) == 1
    assert "product manager" in stub.calls[0]["system"]


def test_a_user_turn_patches_the_brief_and_the_checklist(started, stub):
    scope = started
    sid = store.get_session(scope)["id"]
    stub.load(interview_turn(reply="Got it. Which ports?",
                             checklist_ops=[{"op": "resolve", "id": "CHK-1", "answer_summary": "shoes"},
                                            {"op": "add", "id": "CHK-2", "question": "ports?"}],
                             brief_patch={"products": [{"name": "Runner"}], "pains": ["port delays"]}))
    msgs = sess.run_turn(scope, sid, "We make running shoes; port delays kill us.")
    assert [m.role for m in msgs] == ["agent"]
    thread = store.list_messages(scope, sid)
    assert [m.role for m in thread][-2:] == ["user", "agent"]
    brief, _ = store.current_brief(scope)
    assert [p.name for p in brief.products] == ["Runner"] and brief.pains == ["port delays"]
    by_id = {c.id: c for c in store.list_checklist(scope, "interview")}
    assert by_id["CHK-1"].status == "resolved" and by_id["CHK-2"].status == "open"


def test_the_core_topic_guard_holds_the_stage_open(started, stub):
    scope = started
    sid = store.get_session(scope)["id"]
    stub.load(interview_turn(done=True, done_reason="nothing left"))
    sess.run_turn(scope, sid, "that is everything")
    assert store.get_session(scope)["stage"] == "interview"
    last = store.list_messages(scope, sid)[-1]
    assert "I still need the basics on" in last.text
    assert last.payload["core_gaps"]
    reopened = store.open_checklist(scope, "interview")
    assert any("core topic" in c.why for c in reopened)


def test_a_complete_brief_advances_to_the_data_stage(started, stub):
    scope = started
    sid = store.get_session(scope)["id"]
    stub.load(interview_turn(done=True, done_reason="brief is complete",
                             brief_patch=f.brief().model_dump()),
              data_turn())
    msgs = sess.run_turn(scope, sid, "that is everything")
    assert store.get_session(scope)["stage"] == "data"
    kinds = [m.kind for m in msgs]
    assert "system" in kinds and "form" in kinds
    assert store.open_form(scope).title == "Supply chain backbone"
    assert store.current_brief(scope)[1]["approved"] is True
    assert len(stub.calls) == 2  # the interviewer's turn, then the data agent's opening turn


def test_the_data_stage_advances_to_the_ontology_stage(started, stub):
    scope = started
    sid = store.get_session(scope)["id"]
    store.put_brief(scope, f.brief())
    store.set_session(scope, sid, stage="data")
    stub.load(data_turn(form=None, done=True, done_reason="enough"), ontology_turn())
    sess.run_turn(scope, sid, "done filling in")
    assert store.get_session(scope)["stage"] == "ontology"
    spec, row = store.current_spec(scope)
    assert row["status"] == "draft" and [t.label for t in spec.types] == ["Supplier", "Part", "Product"]


def test_an_invalid_spec_is_sent_back_then_reported(started, stub):
    scope = started
    sid = store.get_session(scope)["id"]
    store.set_session(scope, sid, stage="ontology")
    broken = f.spec(types=[]).model_dump(by_alias=True)
    stub.load(*([ontology_turn(spec=broken)] * 4))
    msgs = sess.run_turn(scope, sid, "design it")
    assert len(stub.calls) == 3  # first draft plus two repair rounds
    assert msgs[-1].role == "system" and "could not produce a valid spec" in msgs[-1].text
    assert store.current_spec(scope) == (None, None)


def test_a_repaired_spec_is_accepted(started, stub):
    scope = started
    sid = store.get_session(scope)["id"]
    store.set_session(scope, sid, stage="ontology")
    stub.load(ontology_turn(spec=f.spec(types=[]).model_dump(by_alias=True)), ontology_turn())
    sess.run_turn(scope, sid, "design it")
    assert store.current_spec(scope)[1]["status"] == "draft"
    assert len(stub.calls) == 2


def test_experts_need_an_approved_ontology(started, stub):
    scope = started
    sid = store.get_session(scope)["id"]
    store.set_session(scope, sid, stage="experts")
    msgs = sess.run_turn(scope, sid, "generate the roles")
    assert "ontology has to be approved" in msgs[-1].text
    assert not stub.calls[1:]  # no LLM call was made


def test_roles_are_generated_and_validated(started, stub, tenants_dir):
    scope = started
    sid = store.get_session(scope)["id"]
    store.put_brief(scope, f.brief())
    row = store.save_spec(scope, f.spec())
    store.set_spec_status(scope, row["id"], "approved")
    store.set_session(scope, sid, stage="experts")
    bad = f.role(focus_types=["Ghost"]).model_dump()
    stub.load(experts_turn(roles=[bad]), experts_turn())
    sess.run_turn(scope, sid, "generate the roles")
    assert len(stub.calls) == 2
    roles = store.list_experts(scope)
    assert [r.name for r in roles] == ["sourcing_risk"] and roles[0].status == "draft"
    assert (tenants_dir / scope.tenant_id / "experts" / "sourcing_risk.md").exists()


def test_resume_reissues_a_turn_that_was_in_flight(started, stub):
    scope = started
    sid = store.get_session(scope)["id"]
    # simulate a crash: the user message is persisted and the turn is marked pending, but no reply was written
    store.append_message(scope, sid, Message(role="user", stage="interview", text="we ship by sea"))
    store.set_pending(scope, sid, {"stage": "interview", "user_text": "we ship by sea"})
    assert store.get_pending(scope)["user_text"] == "we ship by sea"
    stub.load(interview_turn(reply="Which ports?"))
    msgs = sess.resume_pending(scope)
    assert msgs[-1].text == "Which ports?"
    assert store.get_pending(scope) is None


def test_resume_is_a_no_op_without_a_pending_turn(started, stub):
    assert sess.resume_pending(started) == []


def test_goto_flags_downstream_artifacts_stale(started, stub):
    scope = started
    sid = store.get_session(scope)["id"]
    store.put_brief(scope, f.brief())
    store.save_spec(scope, f.spec())
    store.save_expert(scope, f.role())
    store.set_session(scope, sid, stage="experts")
    out = sess.goto(scope, "interview", note="we also ship by rail")
    assert out["stage"] == "interview" and out["stale_flagged"] == 2
    assert store.current_spec(scope)[1]["stale"] is True
    assert store.list_experts(scope)[0].stale is True
    assert store.current_brief(scope)[1]["stale"] is False
    assert store.get_session(scope)["stage"] == "interview"
    last = store.list_messages(scope, sid)[-1]
    assert "Back to interview" in last.text and last.payload["stale_flagged"] == 2


def test_goto_refuses_a_stage_not_yet_reached(started):
    with pytest.raises(sess.StageError) as e:
        sess.goto(started, "experts")
    assert "has not been reached" in str(e.value)
    with pytest.raises(sess.StageError):
        sess.goto(started, "nonsense")


def test_progress_reports_each_stage(started, stub):
    scope = started
    store.put_brief(scope, f.brief())
    p = sess.progress(scope)
    assert [s["stage"] for s in p["stages"]] == ["interview", "data", "ontology", "experts", "ready"]
    interview = p["stages"][0]
    assert interview["current"] and interview["reached"] and interview["open_items"] == 1
    assert interview["artifact"]["gaps"] == []
    assert p["stages"][-1]["reached"] is False


def test_state_is_everything_needed_to_resume(started, stub):
    scope = started
    out = sess.state(scope)
    assert out["stage"] == "interview" and out["tenant"]["name"] == "Acme Shoes"
    assert len(out["messages"]) == 1 and out["open_form"] is None
    assert out["artifacts"]["brief"]["data"]["company"] == "Acme Shoes"
    assert out["artifacts"]["ontology"]["data"] is None and out["artifacts"]["experts"] == []
    assert out["progress"]["stage"] == "interview" and out["busy"] is False


def test_a_provider_failure_is_reported_in_the_thread(started):
    from ripple.llm.base import set_client

    class Broken:
        name = model = "broken"

        def complete(self, **kw):
            from ripple.llm.base import LLMError

            raise LLMError("not logged in")

    scope = started
    sid = store.get_session(scope)["id"]
    set_client(Broken())
    try:
        msgs = sess.run_turn(scope, sid, "hello")
    finally:
        set_client(None)
    assert msgs[-1].role == "system" and "not logged in" in msgs[-1].text
    assert store.get_pending(scope) is None


def test_reonboarding_keeps_the_artifacts_and_goes_back_to_the_interview(started, stub):
    scope = started
    sid = store.get_session(scope)["id"]
    store.put_brief(scope, f.brief(), approved=True)
    row = store.save_spec(scope, f.spec())
    store.set_spec_status(scope, row["id"], "approved")
    store.save_expert(scope, f.role())
    store.set_session(scope, sid, stage="ready")
    store.set_tenant(scope, stage="ready", status="live")
    stub.load(interview_turn(reply="What changed?"))
    out = sess.reonboard(scope, note="new product line")
    assert out["stage"] == "interview" and store.get_tenant(scope)["status"] == "onboarding"
    assert store.current_spec(scope)[1]["stale"] is True
    assert store.current_brief(scope)[0].company == "Acme Shoes"  # nothing was deleted
    assert out["messages"][-1]["text"] == "What changed?"
