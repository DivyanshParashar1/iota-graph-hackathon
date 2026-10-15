"""FormSpec: every field type, repeating groups, conditional visibility, coercion and required checks."""

from __future__ import annotations

import pytest

from ripple.onboarding.agents.data_agent import coerce, missing_required, save_values
from ripple.onboarding.models import FormField, FormSpec
from ripple.onboarding.store import list_answers, save_form
from tests import factories as f


def test_every_declared_field_type_round_trips():
    types = ["text", "longtext", "number", "integer", "currency", "percent", "date", "daterange", "select",
             "multiselect", "boolean", "geo", "file", "group"]
    form = FormSpec(title="All types", fields=[
        FormField(id=f"f_{t}", label=t, type=t, options=["a", "b"],
                  fields=[FormField(id="col", label="col")] if t == "group" else [])
        for t in types])
    assert {fl.type for fl in form.fields} == set(types)
    assert "f_group.col" in form.field_map()


def test_field_ids_are_checked():
    with pytest.raises(ValueError):
        FormField(id="bad id", label="x")
    with pytest.raises(ValueError):
        FormField(id="", label="x")
    assert FormField(id="ok-id_1", label="x").id == "ok-id_1"


@pytest.mark.parametrize("ftype,raw,expected", [
    ("integer", "42", 42), ("integer", "1,200", 1200), ("integer", 7.6, 8),
    ("number", "3.5", 3.5), ("currency", "1,250.50", 1250.5), ("percent", "60%", 60.0),
    ("boolean", "yes", True), ("boolean", "false", False), ("boolean", True, True),
    ("multiselect", "sea", ["sea"]), ("multiselect", ["sea", "air"], ["sea", "air"]),
    ("text", 12, "12"), ("date", "2026-01-01", "2026-01-01"),
    ("geo", {"lat": 1.5, "lon": 2.5}, {"lat": 1.5, "lon": 2.5}),
    ("daterange", {"from": "2026-01-01", "to": "2026-02-01"},
     {"from": "2026-01-01", "to": "2026-02-01"}),
    ("integer", "", None), ("text", None, None),
])
def test_coercion(ftype, raw, expected):
    assert coerce(ftype, raw) == expected


def test_coercion_rejects_rubbish():
    with pytest.raises(ValueError):
        coerce("integer", "about forty")
    with pytest.raises(ValueError):
        coerce("number", "n/a")
    with pytest.raises(ValueError):
        coerce("group", "not a list")


def test_repeating_group_rows(scope):
    form = save_form(scope, f.form())
    rows = [{"name": "GZ Leather", "country": "CN", "lead_time_days": 30, "volume_share": 60},
            {"name": "Rubber Co", "country": "VN", "lead_time_days": 21, "volume_share": 40}]
    save_values(scope, form, {"tier1": rows})
    got = {a.field_id: a.value for a in list_answers(scope, form.id)}
    assert got["tier1"] == rows


def test_an_unknown_field_is_rejected(scope):
    form = save_form(scope, f.form())
    with pytest.raises(ValueError) as e:
        save_values(scope, form, {"ghost": 1})
    assert "no field 'ghost'" in str(e.value)


def test_conditional_fields_are_not_required_when_hidden():
    form = f.form()
    # uses_air is False, so air_share is hidden; supplier_count is required and empty
    assert missing_required(form, {"uses_air": False}) == ["supplier_count"]
    assert missing_required(form, {"supplier_count": 40, "uses_air": False}) == []
    # once the condition is met the hidden field is only required if it says so (air_share does not)
    assert missing_required(form, {"supplier_count": 40, "uses_air": True}) == []


def test_required_group_is_reported():
    form = f.form(fields=[FormField(id="tier1", label="Tier-1", type="group", required=True,
                                     fields=[FormField(id="name", label="Name")])])
    assert missing_required(form, {}) == ["tier1"]
    assert missing_required(form, {"tier1": [{"name": "GZ"}]}) == []


def test_confidence_is_recorded_per_field(scope):
    form = save_form(scope, f.form())
    save_values(scope, form, {"supplier_count": 40}, confidences={"supplier_count": "ballpark"})
    a = list_answers(scope, form.id)[0]
    assert a.confidence == "ballpark" and a.source == "user"


def test_synthetic_values_are_flagged(scope):
    form = save_form(scope, f.form())
    save_values(scope, form, {"supplier_count": 40}, source="synthetic", confidence="synthetic")
    a = list_answers(scope, form.id)[0]
    assert (a.source, a.confidence) == ("synthetic", "synthetic")
