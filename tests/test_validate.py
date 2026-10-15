"""OntologySpec and instance validation - the gate everything generated has to pass before it reaches Cypher."""

from __future__ import annotations

import pytest

from ripple.graph.queries import BadIdentifier, Q, ident
from ripple.onboarding.models import (
    InstanceBatch,
    InstanceEdge,
    InstanceNode,
    PropertySpec,
    RelationshipSpec,
    TypeDisplay,
    TypeSpec,
)
from ripple.onboarding.validate import SpecInvalid, require_valid, validate_instances, validate_spec
from tests import factories as f


def errors_for(**over) -> list[str]:
    return validate_spec(f.spec(**over))


def test_a_good_spec_validates():
    assert validate_spec(f.spec()) == []
    assert require_valid(f.spec()) is not None


def test_reserved_prefix_is_rejected():
    bad = f.spec(types=[TypeSpec(label="_Tenant", id_pattern="X-#",
                                 properties=[PropertySpec(name="name")],
                                 display=TypeDisplay(title_property="name"))], relationships=[], indexes=[])
    assert any("reserved" in e for e in validate_spec(bad))


def test_label_shape_is_rejected():
    for label in ("2Supplier", "Supplier-A", "Supplier name", ""):
        bad = f.spec(types=[TypeSpec(label=label, id_pattern="X-#",
                                     properties=[PropertySpec(name="name")],
                                     display=TypeDisplay(title_property="name"))],
                     relationships=[], indexes=[])
        assert any("plain identifier" in e for e in validate_spec(bad)), label


def test_duplicate_labels_and_patterns():
    t = TypeSpec(label="Supplier", id_pattern="SUP-####", properties=[PropertySpec(name="name")],
                 display=TypeDisplay(title_property="name"))
    errs = validate_spec(f.spec(types=[t, t], relationships=[], indexes=[]))
    assert any("duplicate type label" in e for e in errs)
    t2 = TypeSpec(label="Vendor", id_pattern="SUP-####", properties=[PropertySpec(name="name")],
                  display=TypeDisplay(title_property="name"))
    errs = validate_spec(f.spec(types=[t, t2], relationships=[], indexes=[]))
    assert any("id_pattern" in e for e in errs)


def test_dangling_relationship_endpoints():
    errs = errors_for(relationships=[RelationshipSpec(type="SUPPLIES", **{"from": "Ghost"}, to="Part")])
    assert any("unknown type 'Ghost'" in e for e in errs)
    errs = errors_for(relationships=[RelationshipSpec(type="SUPPLIES", **{"from": "Supplier"}, to="Ghost")])
    assert any("unknown type 'Ghost'" in e for e in errs)


def test_property_types_and_names():
    bad = f.spec(types=[TypeSpec(label="Supplier", id_pattern="SUP-#",
                                 properties=[PropertySpec(name="name"),
                                             PropertySpec(name="LeadTime", type="integer"),
                                             PropertySpec(name="grade", type="enum")],
                                 display=TypeDisplay(title_property="name"))],
                 relationships=[], indexes=[])
    errs = validate_spec(bad)
    assert any("snake_case" in e for e in errs)
    assert any("enum with no options" in e for e in errs)
    bad2 = f.spec(types=[TypeSpec(label="Supplier", id_pattern="SUP-#",
                                  properties=[PropertySpec(name="name", type="uuid")],
                                  display=TypeDisplay(title_property="name"))],
                  relationships=[], indexes=[])
    assert any("unknown type 'uuid'" in e for e in validate_spec(bad2))


def test_title_property_and_id_pattern_are_required():
    errs = validate_spec(f.spec(types=[TypeSpec(label="Supplier",
                                                properties=[PropertySpec(name="name")],
                                                display=TypeDisplay(title_property="label"))],
                                relationships=[], indexes=[]))
    assert any("title_property" in e for e in errs)
    assert any("no id_pattern" in e for e in errs)


def test_index_must_name_a_declared_property():
    from ripple.onboarding.models import IndexSpec

    assert any("not a declared property" in e
               for e in errors_for(indexes=[IndexSpec(label="Supplier", property="ghost")]))
    assert any("unknown type" in e for e in errors_for(indexes=[IndexSpec(label="Ghost", property="id")]))
    assert validate_spec(f.spec(indexes=[IndexSpec(label="Supplier", property="id")])) == []


def test_empty_spec_is_rejected():
    with pytest.raises(SpecInvalid) as e:
        require_valid(f.spec(types=[], relationships=[], indexes=[]))
    assert "declares no types" in str(e.value)


def test_instance_validation():
    spec = f.spec()
    assert validate_instances(spec, f.batch()) == []
    bad = InstanceBatch(nodes=[InstanceNode(label="Ghost", id="G-1")])
    assert any("unknown type 'Ghost'" in e for e in validate_instances(spec, bad))
    bad = InstanceBatch(nodes=[InstanceNode(label="Supplier", id="SUP-1", properties={"ghost": 1})])
    assert any("'ghost' is not declared" in e for e in validate_instances(spec, bad))
    bad = InstanceBatch(nodes=[InstanceNode(label="Supplier", id="SUP-1")],
                        edges=[InstanceEdge(type="SUPPLIES", **{"from": "SUP-1"}, to="PRT-9")])
    assert any("not one of the nodes" in e for e in validate_instances(spec, bad))
    bad = InstanceBatch(nodes=[InstanceNode(label="Supplier", id="SUP-1"),
                               InstanceNode(label="Part", id="PRT-1")],
                        edges=[InstanceEdge(type="SUPPLIES", **{"from": "PRT-1"}, to="SUP-1")])
    assert any("the spec says Supplier" in e for e in validate_instances(spec, bad))
    bad = InstanceBatch(nodes=[InstanceNode(label="Supplier", id="SUP-1"),
                               InstanceNode(label="Part", id="PRT-1")],
                        edges=[InstanceEdge(type="GHOSTS", **{"from": "SUP-1"}, to="PRT-1")])
    assert any("not in the spec" in e for e in validate_instances(spec, bad))


def test_identifier_interpolation_is_guarded():
    assert ident("Supplier") == "Supplier"
    for bad in ("Supplier) DELETE n //", "a b", "", "1x", "a-b"):
        with pytest.raises(BadIdentifier):
            ident(bad)
    rendered = Q("node_lookup", label="Supplier")
    assert "(n:Supplier {id: $id})" in rendered
    with pytest.raises(BadIdentifier):
        Q("node_lookup", label="Supplier) MATCH (x) DETACH DELETE x //")
