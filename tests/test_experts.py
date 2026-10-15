"""Expert roles: validation, the markdown mirror's round trip, and the runtime's prompt and tool contract."""

from __future__ import annotations

import pytest

from ripple.experts import runtime
from ripple.experts.store import export_role, from_markdown, import_dir, to_markdown
from ripple.graph.apply import apply_spec, load_instances
from ripple.onboarding import store
from ripple.onboarding.agents.expert_generator import validate_roles
from ripple.tools.registry import READ_ONLY
from tests import factories as f


@pytest.fixture
def live(scope):
    """A tenant with an approved ontology, instance data loaded and one role saved."""
    spec = f.spec()
    row = store.save_spec(scope, spec)
    store.set_spec_status(scope, row["id"], "approved")
    apply_spec(scope, spec)
    load_instances(scope, spec, f.batch())
    store.save_expert(scope, f.role())
    return scope


# --------------------------------------------------------------------------- validation

def test_a_good_role_validates():
    assert validate_roles([f.role()], f.spec()) == []


def test_no_roles_is_an_error():
    assert any("no roles" in e for e in validate_roles([], f.spec()))


def test_a_role_must_have_an_ontology_footprint():
    errs = validate_roles([f.role(focus_types=[])], f.spec())
    assert any("no ontology footprint" in e for e in errs)
    errs = validate_roles([f.role(focus_types=["Ghost"])], f.spec())
    assert any("not in the approved ontology" in e for e in errs)
    errs = validate_roles([f.role(focus_relationships=["GHOSTS"])], f.spec())
    assert any("focus_relationships" in e for e in errs)


def test_the_justification_must_name_an_ontology_type():
    errs = validate_roles([f.role(justification="Because every company needs one.")], f.spec())
    assert any("names no ontology type" in e for e in errs)


def test_a_prompt_too_short_to_run_is_rejected():
    errs = validate_roles([f.role(system_prompt="You are a nice agent.")], f.spec())
    assert any("too short to run as-is" in e for e in errs)


def test_names_must_be_snake_case_and_unique():
    assert any("snake_case" in e for e in validate_roles([f.role(name="Sourcing Risk")], f.spec()))
    errs = validate_roles([f.role(), f.role()], f.spec())
    assert any("duplicate role name" in e for e in errs)


def test_a_playbook_is_required():
    assert any("no playbook" in e for e in validate_roles([f.role(playbook=[])], f.spec()))


def test_a_mandate_is_required():
    assert any("no mandate" in e for e in validate_roles([f.role(mandate="  ")], f.spec()))


# --------------------------------------------------------------------------- the markdown mirror

def test_markdown_round_trip(scope, tenants_dir):
    role = store.save_expert(scope, f.role())
    text = to_markdown(role)
    assert text.startswith("---\n") and role.system_prompt.strip() in text
    assert 'focus_types: ["Supplier", "Part"]' in text
    back = from_markdown(text)
    assert back.model_dump() == role.model_dump()


def test_export_then_import_restores_the_role(scope, tenants_dir):
    role = store.save_expert(scope, f.role())
    path = export_role(scope, role)
    assert path.name == "sourcing_risk.md"
    store.delete_expert(scope, role.id)
    assert store.list_experts(scope) == []
    imported = import_dir(scope)
    assert [r.name for r in imported] == ["sourcing_risk"]
    assert store.get_expert(scope, role.id).model_dump() == role.model_dump()


def test_an_edited_prompt_file_is_picked_up(scope, tenants_dir):
    role = store.save_expert(scope, f.role())
    path = export_role(scope, role)
    path.write_text(path.read_text().replace("You are the Sourcing Risk Analyst",
                                             "You are the Sourcing Risk Lead"))
    import_dir(scope)
    assert store.get_expert(scope, role.id).system_prompt.startswith("You are the Sourcing Risk Lead")


def test_a_file_without_front_matter_is_rejected():
    with pytest.raises(ValueError):
        from_markdown("You are an agent.")
    with pytest.raises(ValueError):
        from_markdown("---\nname: x\nYou are an agent.")


# --------------------------------------------------------------------------- the runtime

def test_the_system_prompt_is_the_role_plus_the_host_contract(live):
    role = store.get_expert(live, "EXP-sourcing_risk")
    prompt = runtime.system_prompt(live, role)
    assert prompt.startswith("You are the Sourcing Risk Analyst")
    assert "## Your runtime" in prompt and "Acme Shoes" in prompt
    assert "Never invent" in prompt and "describe_ontology" in prompt
    assert role.mandate in prompt
    assert '"label": "Supplier"' in prompt and '"type": "SUPPLIES"' in prompt


def test_tool_allow_list_defaults_to_read_only():
    assert runtime.role_tools(f.role(tools=[])) == list(READ_ONLY)
    assert runtime.role_tools(f.role(tools=["find_nodes", "not_a_tool"])) == ["find_nodes"]
    assert runtime.role_tools(f.role()) == ["describe_ontology", "find_nodes", "neighbours"]


def test_a_role_answers_from_the_graph(live, stub):
    role = store.get_expert(live, "EXP-sourcing_risk")
    stub.load(("", [("find_nodes", {"label": "Supplier"})]),
              ("", [("neighbours", {"label": "Part", "id": "PRT-0001"})]),
              "SUP-0001 and SUP-0002 both supply PRT-0001, so the sole is dual-sourced.")
    out = runtime.ask(live, role, "Is the sole single-sourced?", client=stub)
    assert out["ok"] and out["turns"] == 3
    assert "dual-sourced" in out["text"]
    assert set(out["ids"]) >= {"SUP-0001", "SUP-0002", "PRT-0001"}
    tools_seen = [s["tool"] for s in out["steps"] if s["kind"] == "tool_call"]
    assert tools_seen == ["find_nodes", "neighbours"]


def test_a_role_cannot_reach_a_tool_outside_its_allow_list(live, stub):
    role = store.get_expert(live, "EXP-sourcing_risk")  # its tools exclude `aggregate`
    stub.load(("", [("aggregate", {"label": "Supplier", "property": "tier"})]),
              "I cannot aggregate from here.")
    out = runtime.ask(live, role, "What is the average tier?", client=stub)
    assert out["ok"]
    results = stub.calls[1]["messages"][-1]["content"]
    assert results[0]["is_error"] and "not available" in results[0]["content"]


def test_an_invented_id_is_caught(live, stub):
    role = store.get_expert(live, "EXP-sourcing_risk")
    stub.load(("", [("find_nodes", {"label": "Supplier"})]), "SUP-9999 is the risk.",
              "SUP-0001 is the risk.")
    out = runtime.ask(live, role, "Which supplier is the risk?", client=stub)
    assert out["ok"] and out["text"] == "SUP-0001 is the risk."
    assert any(s["kind"] == "error" for s in out["steps"])


def test_tool_calls_from_a_role_are_attributed_to_it(live, stub):
    role = store.get_expert(live, "EXP-sourcing_risk")
    stub.load(("", [("find_nodes", {"label": "Supplier"})]), "SUP-0001.")
    runtime.ask(live, role, "who?", client=stub)
    rows = live.ops.run("tool_calls_list", {"limit": 10})
    assert any(r["agent"] == "sourcing_risk" and r["tool"] == "find_nodes" for r in rows)
