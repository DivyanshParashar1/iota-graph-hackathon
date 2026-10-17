"""Every structured artifact of onboarding, as pydantic models.

These are the contracts in three directions at once: they are the JSON schema sent to the model, the validation
of what comes back, and the shape the UI reads. Keep them additive - a tenant's stored artifacts are JSON and
must still load after a schema change, so new fields get defaults.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

# --------------------------------------------------------------------------- shared

Stage = Literal["interview", "data", "ontology", "experts", "ready"]
Source = Literal["user", "file", "synthetic", "agent"]
Confidence = Literal["exact", "ballpark", "unknown", "synthetic"]

RESERVED_PREFIX = "_"
PROPERTY_TYPES = ("string", "text", "integer", "float", "boolean", "date", "datetime", "currency", "percent",
                  "geo", "id", "enum", "list")
CARDINALITIES = ("one-to-one", "one-to-many", "many-to-one", "many-to-many")


class Model(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# --------------------------------------------------------------------------- stage 1: brief

class ChecklistOp(Model):
    """One edit the interviewer makes to its own internal checklist of open doubts."""

    op: Literal["add", "resolve", "revise", "drop"]
    id: str = ""
    question: str = ""
    why: str = ""
    answer_summary: str = ""


class ChecklistItem(Model):
    id: str
    stage: Stage = "interview"
    question: str
    why: str = ""
    status: Literal["open", "resolved", "dropped"] = "open"
    answer_summary: str = ""
    created_at: int = 0
    resolved_at: int = 0


class BriefProduct(Model):
    name: str
    description: str = ""
    components: list[str] = Field(default_factory=list)
    volume: str = ""
    markets: list[str] = Field(default_factory=list)


class BriefSupplier(Model):
    kind: str = ""  # what they supply, or the tier ("tier-1 leather", "contract manufacturer")
    name: str = ""
    country: str = ""
    notes: str = ""


class BriefSite(Model):
    kind: str = ""  # factory | warehouse | distribution centre | office | store
    name: str = ""
    location: str = ""
    notes: str = ""


class Brief(Model):
    """The interviewer's structured output. `CORE_TOPICS` must be non-empty before the stage can close."""

    company: str = ""
    industry: str = ""
    summary: str = ""
    products: list[BriefProduct] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    suppliers: list[BriefSupplier] = Field(default_factory=list)
    sites: list[BriefSite] = Field(default_factory=list)
    manufacturing: str = ""
    transport_modes: list[str] = Field(default_factory=list)
    warehousing: str = ""
    distribution: str = ""
    customers: list[str] = Field(default_factory=list)
    markets: list[str] = Field(default_factory=list)
    commercial: str = ""  # contracts, SLAs, incoterms, payment terms
    constraints: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    pains: list[str] = Field(default_factory=list)  # what brought them here
    vocabulary: dict[str, str] = Field(default_factory=dict)  # their words -> what they mean
    unknowns: list[str] = Field(default_factory=list)
    scale: str = ""  # revenue band, headcount, order volume - whatever they gave

    def merge(self, patch: dict | None) -> Brief:
        """A new Brief with `patch` applied: lists and dicts are merged, scalars overwritten when non-empty.

        `brief_patch` is free-form by design - the interviewer sends only the fields that changed, so there is
        no schema to hold it to. That means the patch arrives in whatever shape the model found natural: a
        product can come back as `"Runner (road running)"` where a `BriefProduct` was expected. Coerce what
        can be coerced, drop what cannot, and never let a patch lose a turn's worth of interview."""
        if not patch:
            return self.model_copy(deep=True)
        data = self.model_dump()
        for k, v in patch.items():
            if k not in data or v in (None, "", [], {}):
                continue
            cur = data[k]
            if isinstance(cur, list):
                items = [_coerce_item(k, x) for x in (v if isinstance(v, list) else [v])]
                seen = {_key(x) for x in cur}
                data[k] = cur + [x for x in items if x is not None and _key(x) not in seen]
            elif isinstance(cur, dict):
                data[k] = {**cur, **v} if isinstance(v, dict) else cur
            elif isinstance(v, (str, int, float, bool)):
                data[k] = str(v) if isinstance(cur, str) else v
        try:
            return Brief.model_validate(data)
        except ValidationError as e:  # a field we could not coerce: keep the brief, drop that field's patch
            bad = {str(err["loc"][0]) for err in e.errors() if err["loc"]}
            for k in bad:
                data[k] = self.model_dump().get(k)
            return Brief.model_validate(data)

    def core_gaps(self) -> list[str]:
        """Core topics the stage machine will not let the interviewer close on while they are empty."""
        checks = {
            "company": bool(self.company),
            "products or services": bool(self.products),
            "suppliers or inputs": bool(self.suppliers or self.components),
            "sites": bool(self.sites or self.manufacturing),
            "movement": bool(self.transport_modes or self.distribution),
            "customers or markets": bool(self.customers or self.markets),
            "the pain that brought them here": bool(self.pains),
        }
        return [k for k, ok in checks.items() if not ok]


# A list field whose entries are objects, and the property a bare string should become.
_LIST_ITEMS: dict[str, tuple[type[Model], str]] = {}


def _coerce_item(field: str, value: Any) -> Any:
    """One entry of a list field, in whatever shape the model sent it."""
    spec = _LIST_ITEMS.get(field)
    if spec is None:  # list[str]
        if isinstance(value, (str, int, float)):
            return str(value)
        if isinstance(value, dict):
            return str(value.get("name") or value.get("kind") or next(iter(value.values()), ""))
        return None
    cls, key = spec
    if isinstance(value, cls):
        return value.model_dump()
    if isinstance(value, dict):
        try:
            return cls.model_validate(value).model_dump()
        except ValidationError:
            return None
    if isinstance(value, str):
        return cls.model_validate({key: value}).model_dump()
    return None


def _key(x: Any) -> str:
    if isinstance(x, dict):
        return str(x.get("name") or x.get("kind") or sorted(x.items()))
    return str(x)


_LIST_ITEMS.update({"products": (BriefProduct, "name"), "suppliers": (BriefSupplier, "name"),
                    "sites": (BriefSite, "name")})


class InterviewTurn(Model):
    """The interviewer's structured reply to one user turn."""

    reply: str
    checklist_ops: list[ChecklistOp] = Field(default_factory=list)
    brief_patch: dict = Field(default_factory=dict)
    ask_for_files: list[str] = Field(default_factory=list)
    done: bool = False
    done_reason: str = ""


# --------------------------------------------------------------------------- stage 2: data pack

ColumnType = Literal["text", "longtext", "number", "integer", "currency", "percent", "date", "daterange",
                     "select", "multiselect", "boolean", "geo", "file"]
FieldType = Literal["text", "longtext", "number", "integer", "currency", "percent", "date", "daterange",
                    "select", "multiselect", "boolean", "geo", "file", "group"]


def _check_id(v: str) -> str:
    if not v or not all(c.isalnum() or c in "_-" for c in v):
        raise ValueError("field id must be alphanumeric with _ or -")
    return v


class FormColumn(Model):
    """One column of a repeating group. Columns hold scalars - a group inside a group is not a form, it is a
    schema, and it also makes the JSON schema recursive, which structured output cannot express."""

    id: str
    label: str
    type: ColumnType = "text"
    help: str = ""
    placeholder: str = ""
    unit: str = ""
    required: bool = False
    example: str = ""
    options: list[str] = Field(default_factory=list)
    maps_to: str = ""

    @field_validator("id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        return _check_id(v)


class FormField(Model):
    id: str
    label: str
    type: FieldType = "text"
    help: str = ""
    placeholder: str = ""
    unit: str = ""
    required: bool = False
    example: str = ""
    options: list[str] = Field(default_factory=list)  # select / multiselect
    show_if: dict = Field(default_factory=dict)  # {"field": "<id>", "equals": <value>} - conditional visibility
    fields: list[FormColumn] = Field(default_factory=list)  # type == "group": the columns of a repeating table
    min_rows: int = 0
    max_rows: int = 50
    maps_to: str = ""  # the ontology concept this answer is about, when the agent knows it

    @field_validator("id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        return _check_id(v)


class FormSpec(Model):
    """One round of questions, rendered as a form inside the chat thread."""

    id: str = ""
    round: int = 1
    title: str
    intro: str = ""
    fields: list[FormField]
    status: Literal["open", "submitted"] = "open"
    stale: bool = False  # set by a jump back to the interview: the brief this round was built from changed
    ts: int = 0

    def field_map(self) -> dict[str, FormField | FormColumn]:
        """Every field by id, with a group's columns as `<group id>.<column id>`."""
        out: dict[str, FormField | FormColumn] = {}
        for f in self.fields:
            out[f.id] = f
            for c in f.fields:
                out[f"{f.id}.{c.id}"] = c
        return out


class DataTurn(Model):
    """The data agent's structured reply: a message, optionally a new form round, optionally done."""

    reply: str
    form: FormSpec | None = None
    checklist_ops: list[ChecklistOp] = Field(default_factory=list)
    ask_for_files: list[str] = Field(default_factory=list)
    file_mappings: list[FileMapping] = Field(default_factory=list)
    done: bool = False
    done_reason: str = ""


class FileMapping(Model):
    """A proposed "this field is answered by that column of that upload" link, confirmed by the user."""

    field_id: str
    attachment_id: str
    column: str = ""
    note: str = ""
    confirmed: bool = False


DataTurn.model_rebuild()


class FormAnswer(Model):
    id: str = ""
    form_id: str = ""
    field_id: str
    value: Any = None
    source: Source = "user"
    confidence: Confidence = "exact"
    ts: int = 0


class SynthesizedForm(Model):
    """The demo-only Synthesize pass: one plausible value per field, all flagged synthetic."""

    values: dict[str, Any]
    note: str = ""


# --------------------------------------------------------------------------- stage 3: ontology

class PropertySpec(Model):
    name: str
    type: str = "string"
    unit: str = ""
    required: bool = False
    description: str = ""
    options: list[str] = Field(default_factory=list)


class TypeDisplay(Model):
    icon: str = ""
    color: str = ""
    title_property: str = "name"


class TypeSpec(Model):
    label: str
    description: str = ""
    id_pattern: str = ""
    properties: list[PropertySpec] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    display: TypeDisplay = Field(default_factory=TypeDisplay)


class RelationshipSpec(Model):
    type: str
    from_: str = Field(alias="from")
    to: str
    cardinality: str = "many-to-many"
    properties: list[PropertySpec] = Field(default_factory=list)
    description: str = ""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, serialize_by_alias=True)


class IndexSpec(Model):
    label: str
    property: str


class Coverage(Model):
    unmapped_answers: list[str] = Field(default_factory=list)
    assumed: list[str] = Field(default_factory=list)


class OntologySpec(Model):
    version: int = 1
    types: list[TypeSpec] = Field(default_factory=list)
    relationships: list[RelationshipSpec] = Field(default_factory=list)
    indexes: list[IndexSpec] = Field(default_factory=list)
    rationale: str = ""
    coverage: Coverage = Field(default_factory=Coverage)

    def type_map(self) -> dict[str, TypeSpec]:
        return {t.label: t for t in self.types}


class InstanceNode(Model):
    label: str
    id: str
    properties: dict[str, Any] = Field(default_factory=dict)
    source_ids: list[str] = Field(default_factory=list)  # _FormAnswer / _Attachment ids this came from
    confidence: Confidence = "exact"


class InstanceEdge(Model):
    type: str
    from_id: str = Field(alias="from")
    to_id: str = Field(alias="to")
    properties: dict[str, Any] = Field(default_factory=dict)
    source_ids: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore", populate_by_name=True, serialize_by_alias=True)


class OntologyTurn(Model):
    """The ontology agent's structured reply: a spec plus the message that explains it."""

    reply: str
    spec: OntologySpec
    questions: list[str] = Field(default_factory=list)


class InstanceBatch(Model):
    """The instance data the ontology agent reads out of the data pack, in terms of the approved spec."""

    nodes: list[InstanceNode] = Field(default_factory=list)
    edges: list[InstanceEdge] = Field(default_factory=list)
    notes: str = ""


# --------------------------------------------------------------------------- stage 4: experts

class ExpertRole(Model):
    id: str = ""
    name: str  # machine name, e.g. "sourcing_risk"
    title: str  # human title, e.g. "Sourcing Risk Analyst"
    mandate: str  # what this role owns
    justification: str  # why this supply chain needs it, tied to the ontology
    focus_types: list[str] = Field(default_factory=list)  # node labels it reasons over
    focus_relationships: list[str] = Field(default_factory=list)
    playbook: list[str] = Field(default_factory=list)  # typical questions and the shape of a good answer
    tools: list[str] = Field(default_factory=list)
    system_prompt: str = ""
    status: Literal["draft", "approved", "retired"] = "draft"
    version: int = 1
    origin: Literal["generated", "user"] = "generated"
    stale: bool = False
    ts: int = 0

    @field_validator("system_prompt", "mandate", "justification")
    @classmethod
    def _strip(cls, v: str) -> str:
        """Stripped on the way in, so the markdown mirror round-trips byte for byte."""
        return (v or "").strip()


class ExpertsTurn(Model):
    """The expert generator's structured reply."""

    reply: str
    roles: list[ExpertRole] = Field(default_factory=list)
    dropped: list[str] = Field(default_factory=list)  # roles it considered and rejected, with the reason


# --------------------------------------------------------------------------- transport

class Message(Model):
    id: str = ""
    role: Literal["user", "agent", "system"] = "user"
    agent: str = ""
    stage: Stage = "interview"
    kind: Literal["text", "form", "attachment", "system", "artifact"] = "text"
    text: str = ""
    payload: dict = Field(default_factory=dict)
    ts: int = 0
    seq: int = 0


class AgentStep(Model):
    id: str = ""
    stage: Stage | Literal["incident"] = "interview"  # "incident": the post-onboarding incident pipeline
    agent: str = ""
    kind: str = "llm"  # llm | tool | write | error | stage
    summary: str = ""
    payload: dict = Field(default_factory=dict)
    ms: float = 0.0
    ts: int = 0
