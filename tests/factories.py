"""Artifact builders the tests share: a valid brief, form, spec, instance batch and expert role.

These are fixtures, not fakes: they are the shapes a real agent produces, written by hand so the
deterministic half of the suite can exercise everything downstream of the LLM without one.
"""

from __future__ import annotations

from ripple.onboarding.models import (
    Brief,
    BriefProduct,
    BriefSite,
    BriefSupplier,
    ExpertRole,
    FormColumn,
    FormField,
    FormSpec,
    IndexSpec,
    InstanceBatch,
    InstanceEdge,
    InstanceNode,
    OntologySpec,
    PropertySpec,
    RelationshipSpec,
    TypeDisplay,
    TypeSpec,
)


def brief(**over) -> Brief:
    data = dict(
        company="Acme Shoes", industry="footwear", summary="Mid-size trainer manufacturer.",
        products=[BriefProduct(name="Runner", components=["sole", "upper"], markets=["EU"])],
        components=["sole", "upper", "laces"],
        suppliers=[BriefSupplier(kind="tier-1 leather", name="GZ Leather", country="CN")],
        sites=[BriefSite(kind="factory", name="Dongguan", location="CN")],
        manufacturing="One owned factory plus two contract manufacturers.",
        transport_modes=["sea", "road"], warehousing="One DC in Rotterdam.",
        distribution="Wholesale plus own webshop.", customers=["retail chains"], markets=["EU", "UK"],
        commercial="FOB, 60-day terms, 2% late penalty.", constraints=["no air freight"],
        risks=["single-sourced soles"], pains=["port delays blow up delivery promises"],
        vocabulary={"SKU-R": "the Runner line"}, scale="about 800k pairs a year",
    )
    data.update(over)
    return Brief(**data)


def form(**over) -> FormSpec:
    data = dict(
        title="Supply chain backbone", intro="A few numbers to make the model concrete.",
        fields=[
            FormField(id="supplier_count", label="How many suppliers in total?", type="integer",
                      help="A ballpark is fine.", required=True),
            FormField(id="uses_air", label="Do you ever ship by air?", type="boolean"),
            FormField(id="air_share", label="What share goes by air?", type="percent",
                      show_if={"field": "uses_air", "equals": True}),
            FormField(id="tier1", label="Tier-1 suppliers", type="group", min_rows=1, fields=[
                FormColumn(id="name", label="Name", required=True),
                FormColumn(id="country", label="Country"),
                FormColumn(id="part", label="Part supplied"),
                FormColumn(id="lead_time_days", label="Lead time", type="integer", unit="days"),
                FormColumn(id="volume_share", label="Share of volume", type="percent"),
            ]),
        ],
    )
    data.update(over)
    return FormSpec(**data)


def spec(**over) -> OntologySpec:
    data = dict(
        version=1,
        types=[
            TypeSpec(label="Supplier", description="A company that supplies an input.", id_pattern="SUP-####",
                     properties=[PropertySpec(name="name", type="string", required=True),
                                 PropertySpec(name="country", type="string"),
                                 PropertySpec(name="tier", type="integer")],
                     tags=["Party"], display=TypeDisplay(title_property="name", icon="factory")),
            TypeSpec(label="Part", description="A component of a product.", id_pattern="PRT-####",
                     properties=[PropertySpec(name="name", type="string", required=True),
                                 PropertySpec(name="unit_cost", type="currency", unit="USD")],
                     display=TypeDisplay(title_property="name")),
            TypeSpec(label="Product", description="A finished shoe.", id_pattern="PRD-####",
                     properties=[PropertySpec(name="name", type="string", required=True)],
                     display=TypeDisplay(title_property="name")),
        ],
        relationships=[
            RelationshipSpec(type="SUPPLIES", **{"from": "Supplier"}, to="Part", cardinality="many-to-many",
                             properties=[PropertySpec(name="lead_time_days", type="integer", unit="days"),
                                         PropertySpec(name="volume_share", type="percent")],
                             description="This supplier supplies this part."),
            RelationshipSpec(type="PART_OF", **{"from": "Part"}, to="Product", cardinality="many-to-many",
                             description="This part goes into this product."),
        ],
        indexes=[IndexSpec(label="Supplier", property="country")],
        rationale="Lead time and volume share live on SUPPLIES because they are specific to the pairing.",
    )
    data.update(over)
    return OntologySpec(**data)


def batch(source_ids: list[str] | None = None) -> InstanceBatch:
    src = source_ids or []
    return InstanceBatch(
        nodes=[
            InstanceNode(label="Supplier", id="SUP-0001",
                         properties={"name": "GZ Leather", "country": "CN", "tier": 1}, source_ids=src),
            InstanceNode(label="Supplier", id="SUP-0002",
                         properties={"name": "Rubber Co", "country": "VN", "tier": 1}, confidence="ballpark"),
            InstanceNode(label="Part", id="PRT-0001", properties={"name": "Sole", "unit_cost": 4.2}),
            InstanceNode(label="Product", id="PRD-0001", properties={"name": "Runner"}),
        ],
        edges=[
            InstanceEdge(type="SUPPLIES", **{"from": "SUP-0001"}, to="PRT-0001",
                         properties={"lead_time_days": 30, "volume_share": 60}),
            InstanceEdge(type="SUPPLIES", **{"from": "SUP-0002"}, to="PRT-0001",
                         properties={"lead_time_days": 21, "volume_share": 40}),
            InstanceEdge(type="PART_OF", **{"from": "PRT-0001"}, to="PRD-0001"),
        ],
    )


def role(**over) -> ExpertRole:
    data = dict(
        name="sourcing_risk", title="Sourcing Risk Analyst",
        mandate="Owns supplier concentration and lead-time exposure for every Part.",
        justification="Reasons over Supplier and SUPPLIES to find single-sourced parts, which the brief names "
                      "as the main pain.",
        focus_types=["Supplier", "Part"], focus_relationships=["SUPPLIES"],
        playbook=["Which parts are single-sourced? A good answer names the part and its suppliers."],
        tools=["describe_ontology", "find_nodes", "neighbours"],
        system_prompt="You are the Sourcing Risk Analyst for a shoe manufacturer. " + ("You own the "
                      "question of where a single supplier failure would stop production. ") * 6,
    )
    data.update(over)
    return ExpertRole(**data)
