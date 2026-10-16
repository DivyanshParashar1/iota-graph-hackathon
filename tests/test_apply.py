"""Applying an approved spec: indexes, instance loading, provenance, and the generic graph tools over it."""

from __future__ import annotations

import pytest

from ripple.graph.apply import apply_spec, load_instances
from ripple.onboarding import store
from ripple.onboarding.models import InstanceBatch, InstanceNode
from ripple.onboarding.validate import SpecInvalid
from ripple.tools.base import ToolError
from ripple.tools.registry import TOOLS, call_tool
from tests import factories as f


@pytest.fixture
def loaded(scope):
    """A tenant with an approved spec and the instance batch loaded, including provenance."""
    form = store.save_form(scope, f.form())
    from ripple.onboarding.agents.data_agent import save_values

    save_values(scope, form, {"supplier_count": 40})
    ans = store.list_answers(scope)[0]
    spec = f.spec()
    row = store.save_spec(scope, spec, status="draft")
    store.set_spec_status(scope, row["id"], "approved")
    applied = apply_spec(scope, spec)
    loaded = load_instances(scope, spec, f.batch(source_ids=[ans.id]))
    return {"scope": scope, "spec": spec, "applied": applied, "loaded": loaded, "answer_id": ans.id}


def test_apply_spec_is_idempotent(scope):
    spec = f.spec()
    first = apply_spec(scope, spec)
    assert first["indexes_created"] >= len(spec.types)
    second = apply_spec(scope, spec)
    assert second["indexes_created"] == 0 and second["indexes_existing"] == first["indexes_created"]


def test_apply_spec_refuses_an_invalid_spec(scope):
    with pytest.raises(SpecInvalid):
        apply_spec(scope, f.spec(types=[], relationships=[], indexes=[]))


def test_instances_load_with_provenance(loaded):
    scope = loaded["scope"]
    assert loaded["loaded"] == {"nodes": 4, "edges": 3, "provenance": 1}
    counts = store.instance_counts(scope)
    assert counts["nodes"] == {"Supplier": 2, "Part": 1, "Product": 1}
    assert counts["edges"] == {"SUPPLIES": 2, "PART_OF": 1}
    sources = store.provenance_of(scope, "SUP-0001")
    assert [s["source_id"] for s in sources] == [loaded["answer_id"]]
    assert sources[0]["source_label"] == "_FormAnswer" and sources[0]["source_ref"] == "supplier_count"


def test_edge_properties_are_written(loaded):
    rows = loaded["scope"].ops.query(
        "MATCH (:Supplier {id:'SUP-0001'})-[r:SUPPLIES]->(:Part {id:'PRT-0001'}) "
        "RETURN r.lead_time_days AS lead, r.volume_share AS share")
    assert rows == [{"lead": 30, "share": 60}]


def test_confidence_is_carried_onto_nodes(loaded):
    rows = loaded["scope"].ops.query("MATCH (s:Supplier {id:'SUP-0002'}) RETURN s.confidence AS c")
    assert rows[0]["c"] == "ballpark"


def test_loading_refuses_a_bad_batch(loaded):
    with pytest.raises(SpecInvalid):
        load_instances(loaded["scope"], loaded["spec"],
                       InstanceBatch(nodes=[InstanceNode(label="Ghost", id="G-1")]))


def test_reload_wipes_the_previous_instance_data(loaded):
    scope, spec = loaded["scope"], loaded["spec"]
    smaller = InstanceBatch(nodes=[InstanceNode(label="Supplier", id="SUP-0009",
                                                properties={"name": "Only One"})])
    out = load_instances(scope, spec, smaller, wipe=True)
    assert out["nodes"] == 1
    assert store.instance_counts(scope)["nodes"] == {"Supplier": 1}
    # the onboarding state is untouched by a wipe
    assert store.get_tenant(scope)["name"] == "Acme Shoes"
    assert len(store.list_answers(scope)) == 1


def test_nested_values_are_flattened_for_falkordb(scope):
    spec = f.spec()
    apply_spec(scope, spec)
    store.set_spec_status(scope, store.save_spec(scope, spec)["id"], "approved")
    batch = InstanceBatch(nodes=[InstanceNode(label="Supplier", id="SUP-1",
                                              properties={"name": "Nested", "country": "CN"})],
                          edges=[])
    load_instances(scope, spec, batch)
    rows = scope.ops.query("MATCH (s:Supplier {id:'SUP-1'}) RETURN s.name AS n, s.country AS c")
    assert rows == [{"n": "Nested", "c": "CN"}]


# --------------------------------------------------------------------------- the generic tools

def test_describe_ontology(loaded):
    res = call_tool(loaded["scope"], "describe_ontology", {})
    labels = {t["label"]: t for t in res.data["types"]}
    assert set(labels) == {"Supplier", "Part", "Product"}
    assert labels["Supplier"]["count"] == 2
    assert labels["Supplier"]["title_property"] == "name"
    rels = {r["type"]: r for r in res.data["relationships"]}
    assert rels["SUPPLIES"]["count"] == 2 and rels["SUPPLIES"]["from"] == "Supplier"


def test_find_nodes_and_search(loaded):
    scope = loaded["scope"]
    res = call_tool(scope, "find_nodes", {"label": "Supplier"})
    assert {n["id"] for n in res.data["nodes"]} == {"SUP-0001", "SUP-0002"}
    res = call_tool(scope, "find_nodes", {"label": "Supplier", "query": "rubber"})
    assert [n["id"] for n in res.data["nodes"]] == ["SUP-0002"]
    res = call_tool(scope, "find_nodes", {"label": "Supplier", "query": "SUP-0001"})
    assert [n["id"] for n in res.data["nodes"]] == ["SUP-0001"]


def test_tools_reject_a_label_outside_the_ontology(loaded):
    for tool, args in (("find_nodes", {"label": "Ghost"}), ("get_node", {"label": "Ghost", "id": "X"}),
                       ("neighbours", {"label": "Ghost", "id": "X"}),
                       ("aggregate", {"label": "Ghost", "property": "x"})):
        with pytest.raises(ToolError) as e:
            call_tool(loaded["scope"], tool, args)
        assert "unknown type" in str(e.value)


def test_tools_reject_an_undeclared_property(loaded):
    with pytest.raises(ToolError):
        call_tool(loaded["scope"], "aggregate", {"label": "Supplier", "property": "ghost"})
    with pytest.raises(ToolError):
        call_tool(loaded["scope"], "aggregate", {"label": "Supplier", "group_by": "ghost"})


def test_tools_need_an_approved_ontology(scope):
    with pytest.raises(ToolError) as e:
        call_tool(scope, "describe_ontology", {})
    assert "no approved ontology" in str(e.value)


def test_neighbours_and_aggregate(loaded):
    scope = loaded["scope"]
    res = call_tool(scope, "neighbours", {"label": "Part", "id": "PRT-0001"})
    assert set(res.data["neighbours"]) == {"<-SUPPLIES", "->PART_OF"}
    assert {n["id"] for n in res.data["neighbours"]["<-SUPPLIES"]} == {"SUP-0001", "SUP-0002"}
    res = call_tool(scope, "aggregate", {"label": "Supplier", "property": "tier"})
    assert res.data["count"] == 2 and res.data["max"] == 1
    res = call_tool(scope, "aggregate", {"label": "Supplier", "group_by": "country"})
    assert {g["value"] for g in res.data["groups"]} == {"CN", "VN"}


def test_tool_calls_are_logged(loaded):
    call_tool(loaded["scope"], "find_nodes", {"label": "Supplier"})
    rows = loaded["scope"].ops.run("tool_calls_list", {"limit": 10})
    assert any(r["tool"] == "find_nodes" for r in rows)


def test_every_tool_has_a_schema_and_a_description():
    for name, spec in TOOLS.items():
        assert spec.description and spec.schema["type"] == "object", name
        assert "tenant" not in spec.schema["properties"], name
        assert spec.spec()["name"] == name
