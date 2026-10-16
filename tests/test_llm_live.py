"""The live half of the suite: real LLM calls, run on demand with `-m llm`.

    .venv/bin/pytest -m llm -q                      # every live test
    .venv/bin/pytest -m llm -q -k prompts           # just the schema checks

These need a provider: the `claude` CLI logged in (the default), or OPENROUTER_API_KEY / ANTHROPIC_API_KEY.
They cost money and take minutes, which is why they are not in the default run - but they are the only tests
that prove an agent's prompt produces output the product can use. Transcripts of every call land in
`artifacts/llm_runs/<ts>/` when RIPPLE_LLM_LOG_DIR is set, which `live_env` does.

The user half of the interview is played by a second LLM (`persona.md`), so the whole thing can run
unattended. That is a *test harness*, not a product fake: nothing in `ripple/` knows about it.
"""

from __future__ import annotations

import json
import os
import re
import time

import pytest

from ripple import ROOT
from ripple.config import get_settings
from ripple.llm.base import get_client, set_client
from ripple.llm.structured import ask_model
from ripple.onboarding import session as sess
from ripple.onboarding import store
from ripple.onboarding.agents.common import load_prompt, state_message
from ripple.onboarding.models import (
    DataTurn,
    ExpertsTurn,
    InterviewTurn,
    OntologyTurn,
)
from ripple.onboarding.validate import validate_spec
from tests import factories as f

pytestmark = pytest.mark.llm

RUNS = 3
PERSONA = """You are playing the part of a person from a company that has just arrived at Ripple, a supply chain
product that interviews you and builds a knowledge graph of your business.

You are the operations director of **Northwind Trainers**, a mid-sized shoe manufacturer:

- 850,000 pairs a year, three lines: Runner (road running), Trail, and Court (indoor).
- Soles come from two suppliers: Guangzhou Leather Co in CN (60% of volume, 30-day lead time) and Mekong
  Rubber in VN (40%, 21 days). Uppers come only from Anatolia Textiles in TR, 35 days - your single point of
  failure and your biggest worry. Laces and eyelets are commodity, four suppliers, two weeks.
- You assemble in your own factory in Dongguan (CN) and use one contract manufacturer in Porto (PT) for the
  Court line and European rush orders.
- Finished goods move by sea from Yantian to Rotterdam (32 days) and Felixstowe (34 days); the Porto line goes
  by road. You air-freight about 3% when a launch slips, at four times the cost.
- One distribution centre in Rotterdam, 6 weeks of cover, replenished weekly.
- You sell wholesale to about 40 retail chains across the EU and UK, plus your own webshop (15% of revenue).
  Your three biggest accounts are 45% of revenue, on 60-day terms, FOB Yantian, with a 2% penalty per week
  late after a 5-day grace period.
- The pain: a port delay or an upper shortage blows the delivery promise on the big accounts, and nobody can
  tell you quickly which orders are exposed or which supplier to switch to. You found out about the last
  Anatolia strike from a customer.
- Your words: "the big three" are those accounts; "RTD" is your Rotterdam DC; "cut" is a production run.

Rules:
- Answer only what you are asked, in one or two sentences per question, the way a busy operations director
  would: concrete, with numbers where you have them, "I'd have to check" where you do not.
- Never volunteer the whole brief at once, and never mention that you are playing a part.
- If asked for a file you do not have, say so.
"""


@pytest.fixture(scope="module")
def live_env(tmp_path_factory):
    """Use the configured provider for real, and capture every call to artifacts/llm_runs/<ts>/."""
    os.environ.pop("RIPPLE_LLM_PROVIDER", None)
    run_dir = ROOT / "artifacts" / "llm_runs" / time.strftime("%Y%m%d-%H%M%S")
    os.environ["RIPPLE_LLM_LOG_DIR"] = str(run_dir)
    os.environ["RIPPLE_TENANTS_DIR"] = str(tmp_path_factory.mktemp("tenants"))
    get_settings.cache_clear()
    set_client(None)
    s = get_settings()
    if not s.has_llm:
        pytest.skip("no LLM provider configured (install the `claude` CLI or set a key)")
    yield {"settings": s, "run_dir": run_dir}
    get_settings.cache_clear()


@pytest.fixture
def live_scope(db, live_env, request):
    from ripple.db import TenantScope
    from tests.conftest import tenant_id_for

    s = TenantScope(tenant_id_for(request.node.name), db)
    s.drop()
    store.create_tenant(s, "Northwind Trainers", "footwear")
    yield s


def record(live_env, name: str, payload: dict) -> None:
    d = live_env["run_dir"]
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.json").write_text(json.dumps(payload, default=str, indent=2))


# --------------------------------------------------------------------------- prompts return usable output

@pytest.mark.parametrize("run", range(RUNS))
def test_interviewer_prompt_validates(live_env, run):
    out, _ = ask_model(get_client(), InterviewTurn, load_prompt("interviewer"),
                       [state_message("Your working state",
                                      {"company": "Northwind Trainers", "industry": "footwear",
                                       "brief_so_far": {}, "checklist": [],
                                       "core_topics_still_empty": ["company", "products or services"],
                                       "uploads": []},
                                      instruction="Open the interview with three to five questions.")])
    assert out.reply.strip() and "?" in out.reply
    # "start small": a handful of asks, not a wall. Sub-clauses inside one numbered ask are fine, so count
    # the asks the user actually sees as separate items.
    items = len([ln for ln in out.reply.splitlines() if re.match(r"\s*(\d+[.)]|[-*\u2022])\s", ln)])
    assert items <= 6, f"the opening turn listed {items} questions:\n{out.reply}"
    assert len(out.reply.split()) <= 260, "the opening turn should be short"
    assert out.checklist_ops, "the interviewer must seed its checklist"
    assert all(op.op in ("add", "resolve", "revise", "drop") for op in out.checklist_ops)
    assert not out.done


@pytest.mark.parametrize("run", range(RUNS))
def test_data_agent_prompt_produces_a_usable_form(live_env, run):
    out, _ = ask_model(get_client(), DataTurn, load_prompt("data_agent"),
                       [state_message("Your working state",
                                      {"brief": f.brief(company="Northwind Trainers").model_dump(),
                                       "rounds_so_far": [], "answers": {}, "open_form_id": "",
                                       "checklist": [], "uploads": []},
                                      instruction="Emit your first form round.")])
    assert out.form is not None, "the first turn should emit a form"
    assert 3 <= len(out.form.fields) <= 30
    assert all(fl.label for fl in out.form.fields)
    assert any(fl.type == "group" for fl in out.form.fields), "a list of suppliers belongs in a repeating group"
    ids = [fl.id for fl in out.form.fields]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("run", range(RUNS))
def test_ontologist_prompt_produces_a_valid_spec(live_env, run):
    out, _ = ask_model(get_client(), OntologyTurn, load_prompt("ontologist"),
                       [state_message("Brief, data pack and current spec",
                                      {"brief": f.brief(company="Northwind Trainers").model_dump(),
                                       "data_pack": {"answers": [
                                           {"field_id": "tier1", "label": "Tier-1 suppliers",
                                            "value": [{"name": "Guangzhou Leather", "country": "CN",
                                                       "part": "soles", "lead_time_days": 30}]},
                                           {"field_id": "modes", "label": "Transport modes",
                                            "value": ["sea", "road", "air"]}], "uploads": []},
                                       "current_spec": None, "current_status": ""},
                                      instruction="Design the ontology.")])
    errors = validate_spec(out.spec)
    assert errors == [], errors
    labels = {t.label for t in out.spec.types}
    assert 5 <= len(labels) <= 25, labels
    assert out.spec.rationale.strip()
    assert out.spec.relationships, "a spec with no relationships is a list, not a graph"


@pytest.mark.parametrize("run", range(RUNS))
def test_expert_generator_prompt_produces_grounded_roles(live_env, run):
    from ripple.onboarding.agents.expert_generator import validate_roles

    spec = f.spec()
    out, _ = ask_model(get_client(), ExpertsTurn, load_prompt("expert_generator"),
                       [state_message("Brief and approved ontology",
                                      {"brief": f.brief(company="Northwind Trainers").model_dump(),
                                       "ontology": spec.model_dump(by_alias=True), "existing_roles": []},
                                      instruction="Design the expert roles.")])
    errors = validate_roles(out.roles, spec)
    assert errors == [], errors
    assert 2 <= len(out.roles) <= 10
    for r in out.roles:
        assert len(r.system_prompt) > 400 and r.system_prompt.lower().startswith("you are")


# --------------------------------------------------------------------------- the whole thing, end to end

@pytest.mark.slow
def test_full_onboarding_with_a_persona(db, live_env, request):
    """A shoe manufacturer onboards end to end, its answers supplied by a second LLM playing the user."""
    from ripple.db import TenantScope
    from ripple.onboarding.agents import ontologist
    from ripple.onboarding.events import StepEmitter
    from tests.conftest import tenant_id_for

    client = get_client()
    tid = tenant_id_for("live_full")
    TenantScope(tid, db).drop()
    scope = sess.start(db, "Northwind Trainers", "footwear", tenant_id=tid)
    sid = store.get_session(scope)["id"]
    transcript: list[dict] = []

    def persona_reply(agent_text: str) -> str:
        reply = client.complete(system=PERSONA,
                                messages=[{"role": "user", "content": agent_text}],
                                max_tokens=800, effort="low")
        return (reply.text or "").strip() or "I'd have to check."

    # --- stage 1 and 2: the interview, then the forms, driven by the persona
    for turn in range(28):
        state = sess.state(scope)
        stage = state["stage"]
        if stage in ("ontology", "experts", "ready"):
            break
        last = [m for m in state["messages"] if m["role"] == "agent"]
        assert last, "the agent should have spoken"
        text = last[-1]["text"]
        if state["open_form"]:
            form = store.open_form(scope)
            answers = _fill_form(client, form)
            from ripple.onboarding.agents.data_agent import save_values

            save_values(scope, form, answers, confidences=dict.fromkeys(answers, "ballpark"))
            store.set_form_status(scope, form.id, "submitted")
            transcript.append({"turn": turn, "stage": stage, "form": form.id, "answers": answers})
            sess.run_turn(scope, sid, None)
            continue
        answer = persona_reply(text)
        transcript.append({"turn": turn, "stage": stage, "agent": text, "user": answer})
        sess.run_turn(scope, sid, answer)
    record(live_env, "transcript", {"tenant": scope.tenant_id, "turns": transcript})

    brief, _brief_row = store.current_brief(scope)
    assert brief is not None and brief.core_gaps() == [], brief.core_gaps() if brief else "no brief"
    assert brief.company and brief.pains, "the brief must name the company and the pain"
    assert any("upper" in str(x).lower() or "anatolia" in str(x).lower()
               for x in brief.risks + brief.pains + [s.name for s in brief.suppliers]), \
        "the interview should have surfaced the single-sourced upper"
    record(live_env, "brief", brief.model_dump())

    # --- stage 3: the ontology
    state = sess.state(scope)
    assert state["stage"] in ("ontology", "experts"), state["stage"]
    spec, _row = store.current_spec(scope)
    assert spec is not None, "the ontology agent should have drafted a spec on entering its stage"
    assert validate_spec(spec) == []
    record(live_env, "ontology", spec.model_dump(by_alias=True))

    emit = StepEmitter(scope, "ontology", "ontologist")
    out = ontologist.approve(scope, sid, emit, client=client)
    assert out["nodes"] > 0, "approval must load instance data from the data pack"
    counts = store.instance_counts(scope)
    assert counts["nodes"], counts
    # the batch is recorded separately so scripts/seed_from_run.py can replay the load exactly
    record(live_env, "instances", out.pop("batch", {}))
    record(live_env, "loaded", {"applied": out, "counts": counts})

    msgs = sess.advance(scope, sid, "ontology", reason="approved by the test")
    assert store.get_session(scope)["stage"] == "experts"
    assert msgs

    # --- stage 4: the experts
    roles = store.list_experts(scope)
    assert len(roles) >= 2, [r.name for r in roles]
    labels = {t.label for t in spec.types}
    for r in roles:
        assert set(r.focus_types) <= labels
        assert any(lbl in r.justification for lbl in labels), r.justification
    record(live_env, "experts", [r.model_dump() for r in roles])

    # --- each role answers a real question from the loaded graph
    from ripple.experts import runtime

    answers = []
    for role in roles[:3]:
        store.set_expert_status(scope, role.id, "approved")
        question = role.playbook[0] if role.playbook else f"What do you cover for {brief.company}?"
        res = runtime.ask(scope, role, question, client=client)
        answers.append({"role": role.name, "question": question, "ok": res["ok"], "text": res["text"],
                        "ids": res["ids"], "turns": res["turns"]})
        assert res["ok"], res.get("reason")
        assert res["text"].strip()
    record(live_env, "expert_answers", answers)
    print(f"\n[live] transcript and artifacts in {live_env['run_dir']}")


def _fill_form(client, form) -> dict:
    """The persona filling in a form: one structured call, every value a ballpark."""
    from ripple.onboarding.models import SynthesizedForm

    out, _ = ask_model(client, SynthesizedForm, PERSONA + (
        "\n\nFill in this form about your own company. Return one value per field id. Use the real numbers "
        "from your brief above wherever they apply; leave a field out if you genuinely would not know it."),
        [state_message("Form", {"form": {"title": form.title, "intro": form.intro,
                                          "fields": [x.model_dump() for x in form.fields]}})])
    fields = form.field_map()
    return {k: v for k, v in (out.values or {}).items() if k in fields}


# --------------------------------------------------------------------------- provider smoke

def test_the_configured_provider_answers(live_env):
    reply = get_client().complete(system="Answer with one word.",
                                  messages=[{"role": "user", "content": "Say ok."}], max_tokens=200,
                                  effort="low")
    assert reply.text.strip()


def test_structured_output_works_on_the_configured_provider(live_env):
    from pydantic import BaseModel

    class Tiny(BaseModel):
        answer: str
        count: int

    out, _ = ask_model(get_client(), Tiny, "Answer the question.",
                       [{"role": "user", "content": "How many continents are there? answer='continents'"}])
    assert out.count == 7
