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
    data = {
        "company": "Acme Shoes", "industry": "footwear", "summary": "Mid-size trainer manufacturer.",
        "products": [BriefProduct(name="Runner", components=["sole", "upper"], markets=["EU"])],
        "components": ["sole", "upper", "laces"],
        "suppliers": [BriefSupplier(kind="tier-1 leather", name="GZ Leather", country="CN")],
        "sites": [BriefSite(kind="factory", name="Dongguan", location="CN")],
        "manufacturing": "One owned factory plus two contract manufacturers.",
        "transport_modes": ["sea", "road"], "warehousing": "One DC in Rotterdam.",
        "distribution": "Wholesale plus own webshop.", "customers": ["retail chains"], "markets": ["EU", "UK"],
        "commercial": "FOB, 60-day terms, 2% late penalty.", "constraints": ["no air freight"],
        "risks": ["single-sourced soles"], "pains": ["port delays blow up delivery promises"],
        "vocabulary": {"SKU-R": "the Runner line"}, "scale": "about 800k pairs a year",
    }
    data.update(over)
    return Brief(**data)


def form(**over) -> FormSpec:
    data = {
        "title": "Supply chain backbone", "intro": "A few numbers to make the model concrete.",
        "fields": [
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
    }
    data.update(over)
    return FormSpec(**data)


def spec(**over) -> OntologySpec:
    data = {
        "version": 1,
        "types": [
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
        "relationships": [
            RelationshipSpec(type="SUPPLIES", **{"from": "Supplier"}, to="Part", cardinality="many-to-many",
                             properties=[PropertySpec(name="lead_time_days", type="integer", unit="days"),
                                         PropertySpec(name="volume_share", type="percent")],
                             description="This supplier supplies this part."),
            RelationshipSpec(type="PART_OF", **{"from": "Part"}, to="Product", cardinality="many-to-many",
                             description="This part goes into this product."),
        ],
        "indexes": [IndexSpec(label="Supplier", property="country")],
        "rationale": "Lead time and volume share live on SUPPLIES because they are specific to the pairing.",
    }
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
    data = {
        "name": "sourcing_risk", "title": "Sourcing Risk Analyst",
        "mandate": "Owns supplier concentration and lead-time exposure for every Part.",
        "justification": "Reasons over Supplier and SUPPLIES to find single-sourced parts, which the brief names "
                      "as the main pain.",
        "focus_types": ["Supplier", "Part"], "focus_relationships": ["SUPPLIES"],
        "playbook": ["Which parts are single-sourced? A good answer names the part and its suppliers."],
        "tools": ["describe_ontology", "find_nodes", "neighbours"],
        "system_prompt": "You are the Sourcing Risk Analyst for a shoe manufacturer. " + ("You own the "
                      "question of where a single supplier failure would stop production. ") * 6,
    }
    data.update(over)
    return ExpertRole(**data)


# --------------------------------------------------------------------------- incidents (M8)

def event(**over) -> dict:
    """A webhook body, as a site-alert feed would post it."""
    data = {"source": "site-alerts", "kind": "supplier_site_fire",
            "summary": "Fire reported at GZ Leather's Guangzhou plant (SUP-0001). Production halted; the operator "
                       "expects at least a week before any assessment."}
    data.update(over)
    return data


def report(**over) -> dict:
    """An evidence report whose node ids are all in `batch()`."""
    data = {"situation": "GZ Leather (SUP-0001) is down after a fire. It supplies 60% of soles (PRT-0001); Rubber "
                         "Co (SUP-0002) supplies the other 40% with a 21-day lead time.",
            "evidence": [
                {"id": "E1", "from_agent": "sourcing_risk", "claim": "SUP-0001 supplies 60% of PRT-0001 at a 30-day "
                 "lead time.", "node_ids": ["SUP-0001"], "confidence": "fact"},
                {"id": "E2", "from_agent": "sourcing_risk", "claim": "SUP-0002 supplies the other 40% of PRT-0001 "
                 "at a 21-day lead time.", "node_ids": ["SUP-0002"], "confidence": "ballpark"}],
            "open_questions": ["How much spare capacity SUP-0002 has."]}
    data.update(over)
    return data


def analysis(**over) -> dict:
    data = {"impact_summary": "60% of sole supply is lost from today; Runner production stops when sole stock runs "
                              "out.",
            "metrics": [{"name": "sole_supply_lost", "value": 60, "unit": "%", "basis_evidence_ids": ["E1"]},
                        {"name": "alternative_lead_time", "value": 21, "unit": "days",
                         "basis_evidence_ids": ["E2"]}],
            "time_to_impact_hours": 72, "affected_node_ids": ["SUP-0001"], "assumptions": []}
    data.update(over)
    return data


def comms(**over) -> dict:
    data = {"drafts": [
        {"id": "C1", "recipient_role": "alternate supplier", "recipient_node_id": "SUP-0002", "channel": "email",
         "subject": "Capacity request: soles", "body": "Please confirm how many extra soles you can ship in the "
         "next 4 weeks.", "purpose": "secure capacity"},
        {"id": "C2", "recipient_role": "retail chains", "recipient_node_id": None, "channel": "email",
         "subject": "Runner supply update", "body": "A supplier fire may delay Runner deliveries; we will confirm "
         "dates by Friday.", "purpose": "early notice"}]}
    data.update(over)
    return data


def plan(**over) -> dict:
    data = {"summary": "Either shift sole volume to the second supplier now or wait for an assessment; two "
                       "containment actions are independent.",
            "decision_groups": [
                {"id": "G1", "question": "How do we cover the lost sole volume?", "mode": "exclusive", "options": [
                    {"id": "G1_shift", "title": "Shift sole volume to SUP-0002", "action_kind": "switch supplier",
                     "steps": ["send C1", "raise PO"], "reversible": True, "time_to_effect_hours": 48,
                     "cost_estimate": "small premium", "risk": "capacity unknown", "evidence_ids": ["E2"],
                     "comms_ids": ["C1"]},
                    {"id": "G1_wait", "title": "Wait for the assessment", "action_kind": "hold", "is_wait": True,
                     "evidence_ids": ["E1"], "reversible": True, "time_to_effect_hours": 0}]},
                {"id": "G2", "question": "Which containment actions now?", "mode": "independent", "options": [
                    {"id": "A_notify", "title": "Warn retail chains", "action_kind": "notification",
                     "evidence_ids": ["E1"], "comms_ids": ["C2"], "reversible": False, "time_to_effect_hours": 1},
                    {"id": "A_reserve", "title": "Reserve remaining sole stock for top accounts",
                     "action_kind": "allocation", "evidence_ids": ["E1"], "time_to_effect_hours": 2}]}]}
    data.update(over)
    return data


def jev_body(request: dict, *, noul: float | dict = 0.8, choice: dict | None = None, priority: str = "critical",
             p_priority: float = 0.8, p_choice: float = 0.7) -> dict:
    """A Jev response body for any request, in the shape `ripple/decide/jev.py` documents: every noul answered
    with `noul` (or `noul[qid]`), every choice picking `choice[qid]` (default: its first option) with P=p_choice,
    the priority score picking `priority` with P=p_priority."""
    answers: dict = {}
    for qid, q in request["questions"].items():
        if q["type"] == "noul":
            answers[qid] = {"noul": noul.get(qid, 0.5) if isinstance(noul, dict) else noul}
        elif q["type"] == "choice":
            labels = list(q["criteria"])
            pick = (choice or {}).get(qid) or labels[0]
            rest = (1 - p_choice) / (len(labels) - 1)
            answers[qid] = {"choice": pick, "confidence": p_choice,
                            "probabilities": {lab: (p_choice if lab == pick else rest) for lab in labels}}
        else:
            levels = [c.split(":", 1)[0] for c in q["criteria"]]
            rest = (1 - p_priority) / (len(levels) - 1)
            answers[qid] = {"score": priority,
                            "probabilities": {lev: (p_priority if lev == priority else rest) for lev in levels}}
    return {"model": "typesafe/jev-1.13-20260917", "answers": answers, "usage": {"input_tokens": 1200}}


def scenario() -> dict:
    """eval/decisions/scenario_felixstowe_fire.json: the worked scenario, including its DecisionPacket."""
    import json

    from ripple import ROOT

    return json.loads((ROOT / "eval" / "decisions" / "scenario_felixstowe_fire.json").read_text())
