# Ripple: it interviews your company, builds its supply chain graph, then runs it

> **Graph Hacks: Context for AI Agents** (WeMakeDevs × FalkorDB), Oct 15–18, 2026.
> **Tracks entered: 01 (Agents That Act on Connected Data), 02 (Agent Memory and Coordination), 03 (Company Brain).**

![Ripple](docs/img/landing.png)

Most graph demos ship with a schema. Ripple ships with none. A company arrives at an empty FalkorDB and Ripple
does two jobs, one after the other:

1. **Build.** Four agents talk to the business and turn *"we make shoes"* into a knowledge graph: they interview
   the company, ask for the data they need as forms in the chat, design an ontology and load the data against it,
   then **invent the expert agents that this particular supply chain needs**.
2. **Operate.** When something happens in the real world (a fire at a supplier, a port closing), those experts
   investigate it from the graph, a planner lays out the options, and **Jev, TypeSafe's decision model, makes the
   call**. People approve or reject; for a truly critical event nobody has time to, so policy lets Jev's choice
   stand.

Nothing is hard-wired. There is no DataCo, no shipped ontology, no fallback script. Every agent step is a real
LLM call, and **FalkorDB is the only hard dependency**: the onboarding state, the generated ontology, the
company's data, the expert roles, the incidents and every decision live in it.

```
 BUILD  (onboarding)                                                    OPERATE  (workflow)
 "we make shoes" ─► Interviewer ─► Data agent ─► Ontology agent ─► Expert generator ─► experts ─► event ─► evidence
                    a brief        a data pack    graph + data      agent roles                           ─► options ─► Jev ─► approve
```

## Contents

[The product](#the-product) · [Architecture 1: onboarding](#architecture-1-onboarding-the-agents-that-build-the-graph) ·
[Architecture 2: the workflow](#architecture-2-the-workflow-the-agents-that-operate-it) ·
[The ideas worth stealing](#the-ideas-worth-stealing) · [Run it](#run-it) · [Reference](#the-agents-prompts)

---

## The product

Screenshots are from the running app, on two tenants that Ripple onboarded itself: **Brightwater Brewing** (a craft
brewery) and **Amazon** (an e-marketplace fulfilment network). Nobody wrote their types, roles or prompts. Point
the same agents at a specialty coffee roaster and they ask about green coffee coverage by origin, bonded
warehousing and C-price volatility instead; nothing in this repository knows what coffee is.

### 1. Onboarding: a conversation, not a form

![Onboarding](docs/img/onboarding.png)

A stage rail (**Interview → Data → Ontology → Experts → Ready**) on top, the chat in the middle, and on the right
the **agent trail** (every LLM call, tool call and Jev decision, streamed live) and the **brief** as the
interviewer understands it. You can jump back to any stage you have reached; downstream artifacts are flagged
stale and re-derived. Everything persists in FalkorDB as it happens, so closing the browser mid-answer loses
nothing, including a turn that was in flight when the process died.

### 2. The ontology the agents designed

![Ontology](docs/img/ontology.png)

The schema as a graph (icon and colour per type, cardinality on every link), an inspector that explains the
selected type, and a *Read the model* view that turns every link into a sentence ("Each Supplier is based in one
Region; a Region can have many Suppliers."). Rename a type or ask the agent to merge two: it returns the whole
revised spec and the version history grows. Approving creates the indexes and loads the data pack.

### 3. Expert agents that did not exist an hour ago

![Experts](docs/img/experts.png)

Each role has a mandate, a justification grounded in the ontology (*"Stockouts on Prime items are a stated pain;
this role reasons over FulfillmentCenter, Product, Supplier…"*), the types it reasons over, and a full system
prompt that is stored in the graph **and** at `tenants/<id>/experts/<name>.md`, so you can review it in git, edit
it in a text editor and import it back. Ask any of them a question directly.

### 4. Overview and the instance graph

![Overview](docs/img/overview.png)

Headline numbers, objects by type, **hot spots read off the approved spec** (e.g. *"Parts linked to only one
Supplier: 38%"*, single-sourced and therefore fragile), open incidents and a quick-ask box for every expert.
Beside it, the **Object explorer** (every object, its links and the provenance of every value) and the
**Graph** page (the instance graph with type layers).

![The company's graph](docs/img/graph.png)

### 5. My workspace: a person, their roles and an agent team

![Workspace](docs/img/workspace.png)

Pick who you are; the persona scopes the view to your roles. Your dashboard shows the types
your roles reason over, your hot spots and the incidents that need you, next to a chat with the **agent team**:
an orchestrator that splits your question across the experts, runs them in parallel against the graph and returns
one sourced answer with the delegations attached.

### 6. Incidents: an event in, a decision out

![Incidents](docs/img/incidents.png)

A reported event, Jev's priority distribution (here *critical, 79%*, so no time for a human approval), and each
option as a card: reversibility, cost, risk, numbered steps, Jev's confidence and the evidence ids it rests on.
Green cards were auto-approved by policy and have an **Undo**; anything else waits for a person's Approve / Reject.

### What a judge sees (3 acts, ~4 minutes)

1. **Act 1: nothing up our sleeve (Track 01).** Start with an empty database: `/api/health` shows no graphs. Type a
   company name. The interviewer asks five questions, not fifty, and its private checklist appears in the agent
   trail. Upload a `suppliers.csv`: it is profiled (columns, dtypes, null rates, sample rows) and only the profile
   reaches the agent. The data agent then asks for exactly what is missing as a form; **Synthesize** fills the rest
   and badges every value `synthetic`, so the demo is honest about which numbers are real.
2. **Act 2: the model is yours (Track 01 + 03).** The ontologist drafts the spec; you edit it; you approve it.
   Click any node and **"where did this number come from?"** is answered from the graph, back to the exact form
   field or uploaded column.
3. **Act 3: agents that act (Tracks 01 + 02).** Approve the experts, report *"fire at the Pune fulfilment
   centre"*, and watch the incident pipeline run live: experts consulted, evidence gathered, options planned, Jev
   decides, impact shown on the graph.

Terminal version: `.venv/bin/python scripts/demo.py --company "Northwind Trainers"`. Replay a recorded run with no
LLM calls: `scripts/seed_from_run.py --db var/demo.db`; or load a hand-made footwear tenant with
`scripts/seed_mock.py` (marked `seeded_from="mock"`, objects `confidence="synthetic"`, events left undecided: only
Jev decides).

---

## Architecture 1: onboarding, the agents that build the graph

The build half is a **stage machine** that drives four LLM agents, one structured call per turn, and a host that
enforces the invariants the model must not be trusted with.

```mermaid
flowchart TB
  U[the user<br/>chat · forms · uploads] --> API[FastAPI<br/>onboarding routes + SSE stream]
  API <--> SM

  subgraph SM["onboarding/session.py : the stage machine (resume · jump back · staleness)"]
    direction LR
    S1[interview] --> S2[data] --> S3[ontology] --> S4[experts] --> S5[ready]
  end

  S1 --> A1[Interviewer<br/>private checklist of doubts]
  S2 --> A2[Data agent<br/>asks as in-chat forms<br/>never invents a value]
  S3 --> A3[Ontologist<br/>designs the spec]
  S4 --> A4[Expert generator<br/>roles + system prompts]

  A1 -->|Supply Chain Brief| B[(_Brief)]
  A2 -->|answers + profiled uploads| P[(_FormAnswer · _Attachment)]
  A3 -->|OntologySpec draft| V{{validate_spec<br/>errors go back to the agent, x2}}
  V -->|you approve| AP[graph/apply.py<br/>indexes · load data · provenance]
  A4 -->|ExpertRole| V2{{grounding check<br/>focus types must exist}}
  V2 -->|you approve each| ER[experts/store.py<br/>graph + tenants/id/experts/*.md]

  A1 & A2 & A3 & A4 <--> LLM[ripple/llm<br/>Claude Code CLI · OpenRouter · Anthropic<br/>structured output + repair · tool loop]
  B & P & AP & ER --> FDB[(FalkorDB<br/>tenant_id: _Session _Message _Brief _FormSpec _OntologySpec _ExpertRole<br/>+ the generated types<br/>mem_id: agent memory)]
```

| # | Agent | Job | Produces | Approved by |
|---|---|---|---|---|
| 1 | **Interviewer** | A product manager who is also a supply chain expert. Keeps a private checklist of its own open doubts and works it down, so the interview's length scales with the business. | **Supply Chain Brief** | the agent, gated by a core-topic guard |
| 2 | **Data agent** | Decides what data would make the brief concrete and asks for it as **forms inside the chat**, round by round. Never invents a value. | **Data Pack**: answers, uploaded tables, documents | the agent |
| 3 | **Ontologist** | Designs the graph model from the brief and data pack, then loads the data with provenance. | **Ontology Spec** + a populated graph | **you** |
| 4 | **Expert generator** | Invents the roles this chain needs, justifies each against the ontology, writes its system prompt. | **Expert Roles** | **you**, role by role |

**What makes it robust**

* **The model converses, the host guards the invariants.** The interviewer sets `done: true`; the stage machine
  refuses while `Brief.core_gaps()` is non-empty and reopens a checklist item. An invalid spec or an ungrounded role
  goes back to the agent with the list of errors, up to twice, before the user sees it.
* **The ontology is data, not code.** Cypher cannot parameterise a label, so every generated label passes
  `validate_spec` and then exactly one guarded interpolation point (`graph/queries.ident`). Query text still lives
  in `graph/queries/*.cypher` as `kind: template`.
* **Provenance is an edge.** Every generated node has `HAS_PROVENANCE → _Provenance → FROM_SOURCE → _FormAnswer |
  _Attachment`, so *"where did this come from?"* is one Cypher query.
* **Everything resumes.** State is written to FalkorDB as it happens; a crashed turn is replayed from `pending_json`.

---

## Architecture 2: the workflow, the agents that operate it

Once the experts exist, the same graph runs the day-to-day. There are two entry points, and they deliberately
treat *choice* differently.

### 2a. The incident pipeline (an event arrives)

`POST /api/events/{tenant}` accepts any JSON with a free-text `summary` (a webhook, or the Report box in the UI).
The pipeline turns it into a decision. **LLM agents generate; only Jev decides.**

```mermaid
flowchart TB
  EV[event webhook<br/>POST /api/events/tenant] --> RX[receive → _Incident]
  RX --> J1{{JEV · relevance<br/>one yes/no per expert role}}
  J1 -->|who to consult| ORC

  subgraph LOOP["evidence loop (≤ RIPPLE_INCIDENT_MAX_ROUNDS)"]
    ORC[Orchestrator LLM<br/>writes a question per expert] --> EXP[Expert agents in parallel<br/>read-only graph tools]
    EXP --> J2{{JEV · sufficiency<br/>is the evidence enough?}}
    J2 -->|no| ORC
  end

  J2 -->|yes| REP[Orchestrator<br/>numbered, sourced evidence E1..En]
  REP --> AN[Analyst LLM<br/>impact + metrics + time to impact]
  REP --> CM[Comms LLM<br/>one draft per recipient]
  AN & CM --> PL[Planner LLM<br/>decision groups · options · alternatives<br/>no ranking, no recommendation]
  PL --> PK[DecisionPacket<br/>assembled in code]
  PK --> J3{{JEV · decision<br/>P of each option · priority}}
  J3 --> POL[Policy: fixed thresholds, no model]
  POL -->|critical and P ≥ 0.5| AUTO[auto_approved<br/>no human needed · Undo available]
  POL -->|otherwise| WAIT[awaiting_approval<br/>every option pending]
  WAIT --> H[a person approves / rejects]
  AUTO & H --> IMP[live impact on the graph<br/>nodes touched · metrics · messages · timing]
```

Every agent reply passes a deterministic validator (`ripple/incident/validate.py`): experts that exist, node ids
that actually came back from tools, evidence ids that are in the report, an exclusive group with exactly one
*wait* option. A rejected reply goes back to the model with the problems listed, twice. A run that still fails is
recorded on the incident with its error; it is never lost.

**Who decides what**

| A decision that would be easy to hide in a prompt | Is instead |
|---|---|
| which experts to ask | a Jev yes/no per approved role |
| when to stop questioning | a Jev yes/no after each round, plus a round cap |
| which option to take, and how urgent it is | one Jev `choice` per exclusive group, one yes/no per independent action, one 4-level `score` for priority |
| whether a human must look | policy thresholds on Jev's probabilities (`ripple/decide/policy.py`), not a model |

The LLM agents never see a probability or a verdict (`tests/test_incident.py` checks this). **Jev** is
[TypeSafe's decision model](reference/JEV_VERIFIED.md), not an LLM: it takes a state and typed questions and
returns calibrated probabilities. It lives in `ripple/decide/`, never in `ripple/llm/`. Its state includes the two
or three nearest of nine documented real disruptions (Philips/Nokia/Ericsson 2000, Aisin 1997, Ever Given, Red
Sea, Baltimore bridge…) as precedents. Full spec: [`docs/m8_decision_pipeline.md`](docs/m8_decision_pipeline.md).

**Autonomy is policy.** Priority measures how long a decision can wait for a person, not how high the stakes are.
Only a `critical` event (options disappearing within hours) with P(critical) ≥ 0.5 is auto-approved; an
independent action also needs P(yes) ≥ 0.6. Everything else is queued with Jev's probability beside each option.
"Execute" means the option is marked approved and its live impact is shown on the graph: the nodes it touches, the metrics it moves, the messages it sends and when it takes effect.

### 2b. The workspace chat (a person asks a question)

```mermaid
flowchart LR
  P[a person<br/>assigned to expert roles] --> CH[workspace chat]
  CH --> O[Orchestrator LLM<br/>chooses experts and when to stop]
  O -->|consult_experts: ≤ 6 asks, in parallel| E1[Expert A] & E2[Expert B] & E3[Expert C]
  O -->|describe_ontology| G
  E1 & E2 & E3 --> G[(tenant graph<br/>6 read-only, label-checked tools)]
  E1 & E2 & E3 --> O
  O --> ANS[one sourced answer<br/>with delegations attached]
```

Here an LLM routes, by the owner's choice: it only **answers questions** and never approves or acts. That is the
one sanctioned exception to *only Jev decides*, and it is not extended to anything that decides or acts.

### The expert runtime both paths share

One generic agent runs any role: its system prompt comes from the graph, its tools are the six below, and none
knows a label in advance (`describe_ontology` tells it). Every tool takes a type from the tenant's *approved* spec
and rejects anything else. Answers cite node ids that an **id validator** checked against what the tools actually
returned. That is how a role that was invented ten minutes ago can safely answer from a graph it has never seen.

### Side by side

| | Onboarding (build) | Workflow (operate) |
|---|---|---|
| Trigger | a person starts a company | an event webhook, or a question in the workspace chat |
| Shape | linear stages, but you can jump back | evidence loop → report → options → decision |
| LLM's job | converse, design, write prompts | gather evidence, draft messages, enumerate options |
| Who chooses | the user approves each artifact | **Jev** (incidents); the orchestrator only routes answers (chat) |
| Guardrails | `validate_spec`, core-gap guard, grounding check | referential validator, policy thresholds, Undo |
| Writes | `_Brief`, `_OntologySpec`, instance nodes, `_ExpertRole` | `_Incident`, `_Option`, `_JevDecision`, `_Approval` |
| Streams to | `/api/onboarding/stream` | the same stream, with `stage: "incident"` or `"workspace"` |

---

## The ideas worth stealing

* **The agent's checklist is its working memory.** The interviewer and data agent emit `add`/`resolve`/`revise`/
  `drop` operations on a private checklist persisted as `_ChecklistItem` nodes. It stops repetition and ends the
  interview when the business is understood rather than after N questions.
* **Never invent data.** The data agent asks for a ballpark rather than fill a number in, and every answer carries
  `source` and `confidence`, carried onto the loaded nodes, so an expert can say *"this rests on a ballpark"*.
* **Separate generation from choice.** Making evidence, drafts and options is what LLMs are good at; picking is a
  calibrated-probability problem. Splitting them makes the choice auditable and the autonomy tunable.
* **Validation is a conversation, not an exception.** Errors go back to the agent with the list of problems.
* **No fakes.** There is no scripted mode and no `FakeLLM`: the suite is 1 deterministic tests (no
  network) plus a live half under `-m llm`. Tests reach Jev only through the real client over a mock HTTP transport.

## Run it

```bash
bash scripts/setup_env.sh                  # offline from vendor/
.venv/bin/uvicorn ripple.api.app:app       # the API owns the embedded FalkorDB
cd ui && npm run dev                       # http://localhost:5173
```

The default LLM provider is **Claude Code on your own login**, no API key: Ripple shells out to `claude -p` with its
own tools off. Set `RIPPLE_LLM_PROVIDER=openrouter` + `OPENROUTER_API_KEY`, or `anthropic` + `ANTHROPIC_API_KEY`
to use an API instead (see `.env.example`). Jev needs `OPENROUTER_API_KEY` (or `JEV_BASE_URL` + `JEV_API_KEY`).

```bash
.venv/bin/pytest -q                        # 1 deterministic tests, no network
.venv/bin/pytest -q -m llm                 # the live half: real agent calls
.venv/bin/pytest -q -m jev                 # the real Jev decision model
cd ui && npm run build                     # typecheck + bundle
docker compose up                          # FalkorDB + API + UI in one stack
RIPPLE_DB_MODE=remote .venv/bin/pytest -q  # against docker run -p 6379:6379 falkordb/falkordb:v4.18.3
```

## The agents' prompts

The prompts are the product. They are versioned in git, read at call time, and nothing in the code paraphrases
them.

| Prompt | Words | Opens with |
|---|---|---|
| [`autofill`](ripple/onboarding/agents/prompts/autofill.md) | 288 | You are drafting a plausible made-up answer for a demo of Ripple's onboarding chat. |
| [`data_agent`](ripple/onboarding/agents/prompts/data_agent.md) | 649 | You are the Ripple data agent. The interviewer has handed you a Supply Chain Brief: a readable description |
| [`expert_generator`](ripple/onboarding/agents/prompts/expert_generator.md) | 468 | You are the Ripple expert generator. You decide which expert agents this particular company needs, and you |
| [`interviewer`](ripple/onboarding/agents/prompts/interviewer.md) | 672 | You are the Ripple interviewer: a product manager who is also a supply chain expert. You are talking to |
| [`ontologist`](ripple/onboarding/agents/prompts/ontologist.md) | 593 | You are the Ripple ontology agent. You design the graph model for one company's supply chain, from the |
| [`synthesize`](ripple/onboarding/agents/prompts/synthesize.md) | 230 | You are filling in a demo form with plausible made-up values. |

## The artifact models

These pydantic models are the contract in three directions at once: the JSON schema sent to the model, the
validation of what comes back, and the shape the UI reads.

| Model | Produced by | Fields |
|---|---|---|
| [`Brief`](ripple/onboarding/models.py#L75) | the interviewer | `company`, `industry`, `summary`, `products`, `components`, `suppliers`, `sites`, `manufacturing`, `transport_modes`, `warehousing`, `distribution`, `customers`, `markets`, `commercial`, `constraints`, `risks`, `pains`, `vocabulary`, `unknowns`, `scale` |
| [`InterviewTurn`](ripple/onboarding/models.py#L179) | the interviewer | `reply`, `checklist_ops`, `brief_patch`, `ask_for_files`, `done`, `done_reason` |
| [`FormSpec`](ripple/onboarding/models.py#L247) | the data agent | `id`, `round`, `title`, `intro`, `fields`, `status`, `stale`, `ts` |
| [`DataTurn`](ripple/onboarding/models.py#L269) | the data agent | `reply`, `form`, `checklist_ops`, `ask_for_files`, `file_mappings`, `done`, `done_reason` |
| [`FormAnswer`](ripple/onboarding/models.py#L294) | the user (or Synthesize) | `id`, `form_id`, `field_id`, `value`, `source`, `confidence`, `ts` |
| [`OntologySpec`](ripple/onboarding/models.py#L365) | the ontology agent | `version`, `types`, `relationships`, `indexes`, `rationale`, `coverage` |
| [`OntologyTurn`](ripple/onboarding/models.py#L395) | the ontology agent | `reply`, `spec`, `questions` |
| [`InstanceBatch`](ripple/onboarding/models.py#L403) | the ontology agent | `nodes`, `edges`, `notes` |
| [`ExpertRole`](ripple/onboarding/models.py#L413) | the expert generator (or the user) | `id`, `name`, `title`, `mandate`, `justification`, `focus_types`, `focus_relationships`, `playbook`, `tools`, `system_prompt`, `status`, `version`, `origin`, `stale`, `ts` |
| [`ExpertsTurn`](ripple/onboarding/models.py#L437) | the expert generator | `reply`, `roles`, `dropped` |

## The expert runtime's tools (6)

None of them knows a label in advance. Every one takes a type from the tenant's *approved* spec and is rejected
if it names anything else, which is how one tool set works for every generated ontology.

| Tool | Kind | What it does |
|---|---|---|
| `describe_ontology` | read | This tenant's approved ontology: node types with their properties and instance counts, and the relationships between them. Call this first - the ontology is different for every company. |
| `find_nodes` | read | Nodes of one type, optionally filtered by a substring of their title property or id. |
| `get_node` | read | Every property of one node, by type and id. |
| `neighbours` | read | One node's immediate neighbours, grouped by the relationship that reaches them and its direction. |
| `aggregate` | read | count/sum/avg/min/max of a numeric property of a type, or node counts grouped by a property. |
| `provenance` | read | Where a node's values came from: the onboarding form answers and uploaded files behind it. |

## The graph

### Platform labels (`_`-prefixed, so a generated label can never collide)

| Label | What it holds |
|---|---|
| `_Tenant` | the company: `id`, `name`, `stage`, `status`, `has_synthetic` |
| `_Session` | the onboarding cursor: `stage`, `provider`, `model`, `pending_json` (the turn in flight) |
| `_Message` | every chat turn, with `kind` = `text` / `form` / `attachment` / `system` / `artifact` |
| `_ChecklistItem` | an agent's private open doubts, per stage |
| `_Attachment` | an upload: `sha256`, `kind`, `profile_json`, `summary` |
| `_Brief` | the Supply Chain Brief, versioned, never overwritten |
| `_FormSpec` / `_FormAnswer` | a form round and its per-field answers, with `source` and `confidence` |
| `_OntologySpec` / `_OntologyType` | the generated model, versioned, with `status` `draft`/`approved`/`superseded` |
| `_ExpertRole` | a role: mandate, justification, focus, playbook and its full system prompt |
| `_AgentStep` / `_ToolCall` | the audit and stream trail |
| `_Provenance` | the bridge from a loaded node back to the answer or upload it came from |

Edges: `(_Session)-[:HAS_MESSAGE]->(_Message)`, `(_FormSpec)-[:HAS_ANSWER]->(_FormAnswer)`,
`(_Brief|_OntologySpec)-[:DERIVED_FROM]->(_Message|_FormAnswer|_Attachment)`,
`(_OntologySpec)-[:DEFINES]->(_OntologyType)`, `(_ExpertRole)-[:FOCUSES_ON]->(_OntologyType)`,
`(node)-[:HAS_PROVENANCE]->(_Provenance)-[:FROM_SOURCE]->(_FormAnswer|_Attachment)`.

### Every query (85 files)

Every query Ripple runs lives in `graph/queries/*.cypher` with a header the docs are generated from. The ones
marked `template` carry `{placeholders}` filled from the approved spec — that is how a per-tenant ontology is
queried without string-building Cypher in Python.

### Key queries

**messages_list** — resume: Every message of a session in order, optionally after a sequence number

```cypher
MATCH (:_Session {id: $sid})-[:HAS_MESSAGE]->(m:_Message)
WHERE m.seq > $after
RETURN m.id AS id, m.role AS role, m.agent AS agent, m.stage AS stage, m.kind AS kind, m.text AS text,
       m.payload_json AS payload_json, m.ts AS ts, m.seq AS seq
ORDER BY m.seq
```

**session_get** — the stage cursor: The most recent onboarding session

```cypher
MATCH (s:_Session)
RETURN s.id AS id, s.stage AS stage, s.started_at AS started_at, s.updated_at AS updated_at,
       s.provider AS provider, s.model AS model, s.pending_json AS pending_json
ORDER BY s.started_at DESC
LIMIT 1
```

**ontology_versions** — artifact history: Every ontology spec version, newest first

```cypher
MATCH (o:_OntologySpec)
RETURN o.id AS id, o.version AS version, o.status AS status, o.stale AS stale, o.ts AS ts
ORDER BY o.version DESC
```

**artifacts_mark_stale** — staleness: Flag every artifact of these labels stale (downstream of a changed upstream artifact)

```cypher
MATCH (n)
WHERE any(l IN labels(n) WHERE l IN $labels)
SET n.stale = true
RETURN count(n) AS flagged
```

**instance_merge_nodes** — loading a generated type (template: `{...}` is filled from the approved spec): Load instance rows as nodes of one generated type. Template: {label} comes from the approved spec.

```cypher
UNWIND $rows AS r
MERGE (n:{label} {{id: r.id}})
SET n += r
RETURN count(n) AS merged
```

**instance_merge_edges** — loading a generated relationship (template: `{...}` is filled from the approved spec): Load instance rows as edges of one generated relationship type. Template: {rel}, {from_label}, {to_label}.

```cypher
UNWIND $rows AS r
MATCH (a:{from_label} {{id: r.from}})
MATCH (b:{to_label} {{id: r.to}})
MERGE (a)-[e:{rel}]->(b)
SET e += r.props
RETURN count(e) AS merged
```

**provenance_of** — where did this come from: Where did this number come from? The answers and uploads behind one instance node

```cypher
MATCH (n {id: $id})-[:HAS_PROVENANCE]->(p:_Provenance)-[:FROM_SOURCE]->(src)
RETURN n.id AS node_id, labels(src)[0] AS source_label, src.id AS source_id,
       coalesce(src.field_id, src.filename, '') AS source_ref,
       coalesce(src.value_json, src.summary, '') AS source_value, p.source AS source, p.confidence AS confidence
ORDER BY source_id
```

**neighbourhood** — one node's neighbourhood (template: `{...}` is filled from the approved spec): One node's immediate neighbours and the edge types that reach them. Template: {label}.

```cypher
MATCH (n:{label} {{id: $id}})-[r]-(m)
WHERE NOT any(l IN labels(m) WHERE l STARTS WITH '_')
RETURN type(r) AS rel, startNode(r).id = n.id AS outgoing, labels(m)[0] AS label, m.id AS id,
       coalesce(m.name, m.title, m.id) AS title
ORDER BY rel, id
LIMIT $limit
```

### All 85 query files

#### Onboarding state

| File | Kind | Graph | Purpose |
|---|---|---|---|
| [`attachment_get`](graph/queries/attachment_get.cypher) | read | ops | One upload by id |
| [`attachment_upsert`](graph/queries/attachment_upsert.cypher) | write | ops | Record an upload with its profile |
| [`checklist_list`](graph/queries/checklist_list.cypher) | read | ops | A stage's checklist items (the agent's working memory; never rendered to the user) |
| [`checklist_upsert`](graph/queries/checklist_upsert.cypher) | write | ops | Create or update one internal checklist item of a stage agent |
| [`message_append`](graph/queries/message_append.cypher) | write | ops | Append one chat message to a session |
| [`message_max_seq`](graph/queries/message_max_seq.cypher) | read | ops | The highest message sequence number in a session (0 when empty) |
| [`session_get`](graph/queries/session_get.cypher) | read | ops | The most recent onboarding session |
| [`session_set`](graph/queries/session_set.cypher) | write | ops | Patch session fields (stage, updated_at, pending_json) |
| [`session_upsert`](graph/queries/session_upsert.cypher) | write | ops | Create or update the onboarding session (stage cursor, provider, model) |
| [`step_append`](graph/queries/step_append.cypher) | write | ops | Record one agent step (the audit and stream trail) |
| [`steps_count`](graph/queries/steps_count.cypher) | read | ops | How many agent steps there are (optionally one stage) |
| [`steps_list`](graph/queries/steps_list.cypher) | read | ops | Agent steps in order, newest last (optionally one stage); skip the oldest to get the newest $limit |
| [`tenant_counts`](graph/queries/tenant_counts.cypher) | read | ops | Node and edge totals of a graph |
| [`tenant_get`](graph/queries/tenant_get.cypher) | read | ops | The tenant node (id, name, stage, status, flags) |
| [`tenant_set`](graph/queries/tenant_set.cypher) | write | ops | Patch tenant fields (stage, status, has_synthetic, name) |
| [`tenant_upsert`](graph/queries/tenant_upsert.cypher) | write | ops | Create or update the tenant node that owns this graph |

#### Artifacts and versioning

| File | Kind | Graph | Purpose |
|---|---|---|---|
| [`answer_upsert`](graph/queries/answer_upsert.cypher) | write | ops | Save one form answer (per-field autosave); re-saving a field overwrites it |
| [`answers_list`](graph/queries/answers_list.cypher) | read | ops | Every answer of the data pack (optionally one form round) |
| [`artifacts_mark_stale`](graph/queries/artifacts_mark_stale.cypher) | write | ops | Flag every artifact of these labels stale (downstream of a changed upstream artifact) |
| [`brief_current`](graph/queries/brief_current.cypher) | read | ops | The latest brief version |
| [`brief_upsert`](graph/queries/brief_upsert.cypher) | write | ops | Store a new version of the Supply Chain Brief (versions are never overwritten) |
| [`brief_versions`](graph/queries/brief_versions.cypher) | read | ops | Every brief version, newest first (artifact history) |
| [`derived_from`](graph/queries/derived_from.cypher) | write | ops | Record that an artifact was derived from the messages, answers and uploads listed |
| [`expert_delete`](graph/queries/expert_delete.cypher) | write | ops | Delete an expert role and its edges |
| [`expert_focus_link`](graph/queries/expert_focus_link.cypher) | write | ops | Link an expert role to the ontology types it reasons over |
| [`expert_get`](graph/queries/expert_get.cypher) | read | ops | One expert role by id |
| [`expert_set_status`](graph/queries/expert_set_status.cypher) | write | ops | Approve / retire / redraft one expert role |
| [`expert_upsert`](graph/queries/expert_upsert.cypher) | write | ops | Create or update an expert role (generated or user-authored) |
| [`experts_list`](graph/queries/experts_list.cypher) | read | ops | Every expert role, newest first |
| [`formspec_get`](graph/queries/formspec_get.cypher) | read | ops | One form round by id |
| [`formspec_set_status`](graph/queries/formspec_set_status.cypher) | write | ops | Mark a form round open or submitted |
| [`formspec_upsert`](graph/queries/formspec_upsert.cypher) | write | ops | Store one round of the data agent's in-chat form |
| [`formspecs_list`](graph/queries/formspecs_list.cypher) | read | ops | Every form round in order |
| [`ontology_approved`](graph/queries/ontology_approved.cypher) | read | ops | The approved ontology spec the instance data is loaded against |
| [`ontology_current`](graph/queries/ontology_current.cypher) | read | ops | The latest ontology spec of any status |
| [`ontology_set_status`](graph/queries/ontology_set_status.cypher) | write | ops | Approve / supersede one ontology spec version |
| [`ontology_supersede_others`](graph/queries/ontology_supersede_others.cypher) | write | ops | Mark every approved spec other than this one superseded |
| [`ontology_types_list`](graph/queries/ontology_types_list.cypher) | read | ops | The declared types of one spec |
| [`ontology_types_upsert`](graph/queries/ontology_types_upsert.cypher) | write | ops | One _OntologyType node per label of a spec, so experts can FOCUSES_ON them |
| [`ontology_upsert`](graph/queries/ontology_upsert.cypher) | write | ops | Store a new version of the generated ontology spec |
| [`ontology_versions`](graph/queries/ontology_versions.cypher) | read | ops | Every ontology spec version, newest first |

#### The generated ontology (templates)

| File | Kind | Graph | Purpose |
|---|---|---|---|
| [`aggregate_property`](graph/queries/aggregate_property.cypher) | template | ops | count / sum / avg / min / max of one property of one generated type. Template: {label}, {prop}. |
| [`group_by_property`](graph/queries/group_by_property.cypher) | template | ops | Count nodes of one generated type grouped by a property. Template: {label}, {prop}. |
| [`instance_counts`](graph/queries/instance_counts.cypher) | read | ops | Instance node counts per generated label (platform labels excluded) |
| [`instance_edge_counts`](graph/queries/instance_edge_counts.cypher) | read | ops | Instance edge counts per generated relationship type (platform edges excluded) |
| [`instance_merge_edges`](graph/queries/instance_merge_edges.cypher) | template | ops | Load instance rows as edges of one generated relationship type. Template: {rel}, {from_label}, {to_label}. |
| [`instance_merge_nodes`](graph/queries/instance_merge_nodes.cypher) | template | ops | Load instance rows as nodes of one generated type. Template: {label} comes from the approved spec. |
| [`instance_wipe`](graph/queries/instance_wipe.cypher) | write | ops | Delete every instance node of the generated ontology (re-load after a new approved spec) |
| [`neighbourhood`](graph/queries/neighbourhood.cypher) | template | ops | One node's immediate neighbours and the edge types that reach them. Template: {label}. |
| [`node_lookup`](graph/queries/node_lookup.cypher) | template | ops | One node of a generated type by id, with every property. Template: {label}. |
| [`nodes_of_type`](graph/queries/nodes_of_type.cypher) | template | ops | Nodes of one generated type (paged). Template: {label}. |
| [`provenance_link`](graph/queries/provenance_link.cypher) | write | ops | Link generated instance nodes back to the form answers and uploads they came from |
| [`provenance_of`](graph/queries/provenance_of.cypher) | read | ops | Where did this number come from? The answers and uploads behind one instance node |
| [`provenance_wipe`](graph/queries/provenance_wipe.cypher) | write | ops | Delete provenance nodes whose instance node is gone (after an instance wipe) |
| [`search_nodes`](graph/queries/search_nodes.cypher) | template | ops | Case-insensitive substring search over the title property of one generated type. Template: {label}, {prop}. |

#### Platform

| File | Kind | Graph | Purpose |
|---|---|---|---|
| [`meta_stats`](graph/queries/meta_stats.cypher) | read | ops | Label and relationship-type counts (db.meta.stats) for the ontology page |
| [`tool_call_log`](graph/queries/tool_call_log.cypher) | write | ops | Record one tool call so an expert's answer can be traced back to the queries behind it |
| [`tool_calls_list`](graph/queries/tool_calls_list.cypher) | read | ops | Recent tool calls (newest first) |

#### Other

| File | Kind | Purpose |
|---|---|---|
| [`approval_append`](graph/queries/approval_append.cypher) | write | Record an approval or rejection of an option, by a person or by the auto-approval policy |
| [`approvals_list`](graph/queries/approvals_list.cypher) | read | Every approval and rejection on one incident, in order |
| [`attachments_list`](graph/queries/attachments_list.cypher) | read | Every upload of this tenant with its profile |
| [`chat_message_append`](graph/queries/chat_message_append.cypher) | write | Append one message (the employee's, or the orchestrator's answer with its delegations) to a thread |
| [`chat_messages_list`](graph/queries/chat_messages_list.cypher) | read | Every message of one chat thread in order |
| [`chat_thread_delete`](graph/queries/chat_thread_delete.cypher) | write | Delete one chat thread and its messages |
| [`chat_thread_upsert`](graph/queries/chat_thread_upsert.cypher) | write | Create or update one employee's chat thread with the workspace orchestrator |
| [`chat_threads_list`](graph/queries/chat_threads_list.cypher) | read | One employee's chat threads, most recently active first |
| [`create_index`](graph/queries/create_index.cypher) | template | One index for a generated type. Template: {label}, {prop}; raises when the index already exists. |
| [`employee_delete`](graph/queries/employee_delete.cypher) | write | Delete an employee with their chat threads and messages |
| [`employee_upsert`](graph/queries/employee_upsert.cypher) | write | Create or update an employee (a person who uses the workspace) and their assigned expert roles |
| [`employees_list`](graph/queries/employees_list.cypher) | read | Every employee, by name |
| [`graph_edges_between`](graph/queries/graph_edges_between.cypher) | read | The edges among a given set of instance node ids (the graph view's links) |
| [`graph_nodes_sample`](graph/queries/graph_nodes_sample.cypher) | read | A sample of the generated instance nodes for the graph view (platform state excluded) |
| [`incident_concerns_link`](graph/queries/incident_concerns_link.cypher) | write | Link an incident to the instance nodes its evidence names (unlabelled match: incidents name few ids) |
| [`incident_get`](graph/queries/incident_get.cypher) | read | One incident with every stored property (the JSON artifacts are decoded in ripple/incident/store.py) |
| [`incident_option_set`](graph/queries/incident_option_set.cypher) | write | Patch one option (its status after an approval, a rejection or a superseding choice) |
| [`incident_option_upsert`](graph/queries/incident_option_upsert.cypher) | write | Create or update one proposed option of an incident, with Jev's probability and the policy verdict |
| [`incident_options_list`](graph/queries/incident_options_list.cypher) | read | Every option of one incident, by group and Jev's rank |
| [`incident_upsert`](graph/queries/incident_upsert.cypher) | write | Create or update an incident (one reported event and everything the pipeline made of it) |
| [`incidents_list`](graph/queries/incidents_list.cypher) | read | Incidents, newest first, without their artifacts |
| [`jev_decision_append`](graph/queries/jev_decision_append.cypher) | write | Record one Jev call of an incident: why it was asked, the request, the answers and the build |
| [`jev_decisions_list`](graph/queries/jev_decisions_list.cypher) | read | Every Jev call of one incident, in order |
| [`messages_list`](graph/queries/messages_list.cypher) | read | Every message of a session in order, optionally after a sequence number |
| [`nodes_by_ids`](graph/queries/nodes_by_ids.cypher) | read | Instance nodes by id whatever their generated type (an option's live impact); never platform nodes |
| [`nodes_with_value`](graph/queries/nodes_with_value.cypher) | template | Nodes of one generated type whose property equals a value (an overview hot spot's examples). Template: {label}, {prop}. |
| [`single_linked_targets`](graph/queries/single_linked_targets.cypher) | template | How many nodes of a type have exactly one partner over a many-to-many link (concentration risk). Template: {from_label}, {rel}, {to_label}. |

## Measured numbers

_Generated by `scripts/report_numbers.py` on 2026-10-18 (3.13.7 on arm64)._

### The platform

| | |
|---|---|
| Query files (`graph/queries/*.cypher`) | 85 |
| Tools in the registry | 6 |
| Agent prompts | 6 files, 2,900 words |
| Python | 68 files, 7,794 lines |
| UI | 34 files, 7,546 lines |
| Deterministic suite | 1 tests in 16.6s |

### One tenant's graph (12 generated types, 500 instances each)

| | |
|---|---|
| Tenant create + platform indexes | 20.2 ms |
| Apply the generated spec (24 indexes) | 6.8 ms |
| Load 6,000 nodes + 5,500 edges | 151.1 ms (39,709 nodes/s) |
| Graph on disk | 0.4 MB |

### Tool latency (20 runs each)

| Tool | p50 | p95 |
|---|---|---|
| `describe_ontology` | 16.6 ms | 17.0 ms |
| `find_nodes` | 1.6 ms | 1.7 ms |
| `get_node` | 0.9 ms | 0.9 ms |
| `neighbours` | 0.9 ms | 1.2 ms |
| `aggregate` | 1.0 ms | 1.1 ms |

## FalkorDB notes

`reference/FALKORDB_VERIFIED.md` records what was verified by running it (embedded `falkordblite` 0.10.0, graph
module v4.18.3). The ones this build turns on:

* **Map-valued properties are rejected.** Instance properties are flattened one level and anything deeper is
  JSON-encoded (`graph/apply.py:_flat`).
* **`MERGE` on an unlabelled pattern scans the graph.** Loading edges grouped by `(relationship, from label, to
  label)` so both `MATCH`es hit an id index made the instance load **~50× faster** (16.3 s → 0.33 s for 11.5k
  entities).
* **Re-running `CREATE INDEX` raises.** Both the platform schema and `apply_spec` treat "already exists" as
  success, so approving an ontology twice is safe.
* **One process owns an embedded `.db` file.** The API process owns it; everything else goes through the HTTP
  API or runs in-process.


## Team

Team Iota: Divyansh Parashar (developer), Virag Tiwari (co-founder, Orange Cat Technologies) and Vaibhav, all
final-year undergraduates.

## Licence and provenance

MIT, see [LICENCE](LICENSE). AI-assisted build: [`AI_DISCLOSURE.md`](AI_DISCLOSURE.md). The build plan and its
milestones: [`plan.md`](plan.md); the original pitch: [`idea.md`](idea.md); v1's plan, for the record:
[`docs/plan_v1_dataco.md`](docs/plan_v1_dataco.md).
