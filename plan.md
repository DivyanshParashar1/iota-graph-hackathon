# Ripple v2: Build Plan — Agentic Onboarding and a Per-Tenant Supply Chain Brain

This plan replaces the v1 build plan (archived at `docs/plan_v1_dataco.md`). v1 built a supply chain control
tower hard-wired to one dataset (DataCo) and one hand-written ontology. v2 keeps the idea of a graph-native
agent platform but makes it **data independent**: the product no longer ships a supply chain, it **interviews a
company and builds one**.

When this file disagrees with `idea.md`, this file wins. When it disagrees with
`reference/FALKORDB_VERIFIED.md` (FalkorDB/Cypher syntax), that file wins.

---

## 0. Ground rules for v2

1. **FalkorDB is the only hard requirement.** It is the primary database: onboarding state, the generated
   ontology, the tenant's instance data, the expert roles and all agent memory live in it.
2. **No fakes, no scripts.** Scripted agent modes, `FakeLLM` and recorded-LLM test doubles are removed. Every
   agent step is a real LLM call. Tests are split into deterministic non-LLM tests and live LLM tests
   (§8).
3. **Default LLM provider: the Claude Code bridge** (`ripple/agents/claude_code.py` +
   `ripple/claude_code_bridge.py`), which runs on the local `claude` CLI login — no API key needed.
   **OpenRouter stays** as a selectable provider for later use. The Anthropic-direct client stays only if it
   costs nothing to keep.
4. **Product quality over deadline.** Each milestone ends with its tests green and a commit. Nothing is
   declared done on the strength of a code path that was never executed against a real LLM.
5. `CLAUDE.md`'s remaining rules (queries in `graph/queries/*.cypher`, one process per embedded `.db`,
   generated README, prefer the vendored dependency set) are **guidelines**: follow them unless a milestone
   has a stated reason not to. Query placement is the one worth defending — see the open question in §9.1.
6. **One user = one tenant.** A tenant is created the moment onboarding starts and is the scope for
   everything that follows.

---

## 1. The product in one page

A new company arrives at an empty Ripple. Four agents, in a chat, turn "we make shoes" into a running
knowledge-graph application:

| # | Agent | Role | Produces |
|---|---|---|---|
| 1 | **Interviewer** | Product manager + supply chain expert. Conversational, adaptive, keeps an internal checklist of its own open doubts and works it down. | A structured **Supply Chain Brief** |
| 2 | **Data agent** | Decides what data is needed to make the brief concrete, and asks for it as **in-chat forms** (iterative, multi-round), plus file uploads. | A **Data Pack**: answers, uploaded tables, documents |
| 3 | **Ontology agent** | Designs the tenant's ontology (node types, relationships, properties, identifiers) from the brief + data pack, and loads the data into FalkorDB against it. | An approved **Ontology Spec** + a populated graph |
| 4 | **Expert generator** | Invents the expert roles this particular supply chain needs (logistics, sourcing, quality, customs, demand…), justifies each one, and writes its system prompt. | Approved **Expert Roles**, each a real runtime agent |

Onboarding is **non-linear**: the user can go back to any earlier stage at any time, and downstream artifacts
are marked stale and re-derived. Everything persists in FalkorDB, so closing the browser loses nothing.
Everything the agents do is streamed live to the UI.

What runs *after* onboarding (the main application) is **not specified yet** and is deliberately out of scope
until §10.

---

## 2. Target architecture

```
ripple/
  config.py                   # settings: provider, model, effort, db mode, paths
  db.py                       # FalkorDB access + TenantScope           (kept from v1)
  graph/
    queries.py                # named .cypher loader                     (kept)
    queries/*.cypher          # platform queries (onboarding, ontology, experts)
    schema_platform.cypher    # indexes for platform-level labels
    apply.py                  # applies a generated OntologySpec to a tenant graph (indexes, constraints)
  llm/
    base.py                   # LLMClient protocol: complete(system, messages, tools|schema) -> reply
    claude_code.py            # Claude Code CLI / host bridge provider   (adapted from v1)
    openrouter.py             # OpenRouter provider                      (adapted from v1)
    loop.py                   # one tool-using agent loop (logging, streaming, id validation)
    structured.py             # JSON-schema structured output + repair
  onboarding/
    store.py                  # all reads/writes of onboarding state in FalkorDB
    models.py                 # pydantic models: Brief, Checklist, FormSpec, DataPack, OntologySpec, ExpertRole
    session.py                # stage machine, staleness/versioning, resume, go-back
    events.py                 # in-process pub/sub -> SSE
    attachments.py            # upload intake: csv/tsv/json/md/txt/xlsx/pdf/docx -> text + tables + profile
    synth.py                  # "Synthesize" (demo only): LLM-autofills a FormSpec, marks every value synthetic
    agents/
      interviewer.py          # stage 1
      data_agent.py           # stage 2
      ontologist.py           # stage 3
      expert_generator.py     # stage 4
      prompts/*.md            # the four system prompts, versioned in git
  experts/
    model.py                  # ExpertRole: name, mandate, justification, system prompt, tools, ontology focus
    store.py                  # CRUD in FalkorDB + export/import to tenants/<tenant>/experts/*.md
    runtime.py                # generic ExpertAgent: runs any role against the tenant graph
  tools/
    base.py registry.py       # tool protocol + registry                 (kept, contents re-cut in M5)
    graph_tools.py            # ontology-aware, tenant-generic graph tools (replaces DataCo-specific tools)
  api/
    app.py                    # FastAPI
    routes_onboarding.py      # session, chat, forms, uploads, stream
    routes_ontology.py        # draft, edit, approve, inspect
    routes_experts.py         # list, CRUD, run
    routes_meta.py            # health, tenant, config
ui/src/
  pages/Onboarding.tsx        # the whole four-stage chat experience
  pages/Ontology.tsx          # review / edit / approve the generated graph model
  pages/Experts.tsx           # review / approve / CRUD expert roles
  components/Chat/*           # message list, streaming, stage rail, InlineForm, FileDrop
  components/GraphView.tsx    # kept, re-pointed at the generated ontology
tenants/<tenant_id>/          # file-side mirror: experts/*.md, uploads/, exports/
```

### Removed in v2 (archived by git tag `v1-dataco`)

`ripple/ontology.py` (static ontology), `ripple/ingest/` (dataco, synth, load_synth, docs, delta, build),
`ripple/scenarios.py`, `ripple/geo.py`, `ripple/agents/{sentinel,analyst,planner,comms,orchestrator,planning,runtime}.py`,
the scripted-mode branches everywhere, `FakeLLM`, `eval/`, `data/raw/`, `data/synthetic/`, `data/scenarios/`,
the DataCo-shaped queries in `graph/queries/`, and the v1 UI pages
(ControlTower, Incident, Actions, Brain, Memory). The incident/action/memory **concepts** return in the main
application (§10) rebuilt on the generated ontology — not as DataCo code.

---

## 3. Data model (platform labels, FalkorDB)

Two graphs per tenant, as in v1: `tenant_<id>` (ontology + instance data) and `mem_<id>` (agent memory).
Onboarding state lives in `tenant_<id>` under platform labels prefixed `_` so they can never collide with a
generated label.

| Label | Key properties |
|---|---|
| `_Tenant` | `id`, `name`, `created_at`, `stage`, `status` (`onboarding`/`live`) |
| `_Session` | `id`, `stage`, `started_at`, `updated_at`, `provider`, `model` |
| `_Message` | `id`, `role` (`user`/`agent`), `agent`, `stage`, `kind` (`text`/`form`/`attachment`/`system`), `text`, `payload_json`, `ts`, `seq` |
| `_ChecklistItem` | `id`, `stage`, `question`, `why`, `status` (`open`/`resolved`/`dropped`), `answer_summary`, `created_at`, `resolved_at` |
| `_Attachment` | `id`, `filename`, `mime`, `bytes`, `sha256`, `kind` (`table`/`document`), `profile_json`, `text_path`, `ts` |
| `_Brief` | `id`, `version`, `json`, `approved`, `created_at` — the interviewer's structured output |
| `_FormSpec` | `id`, `round`, `title`, `intro`, `fields_json`, `status` (`open`/`submitted`), `ts` |
| `_FormAnswer` | `id`, `form_id`, `field_id`, `value_json`, `source` (`user`/`file`/`synthetic`), `confidence`, `ts` |
| `_OntologySpec` | `id`, `version`, `json`, `status` (`draft`/`approved`/`superseded`), `rationale`, `ts` |
| `_ExpertRole` | `id`, `name`, `title`, `mandate`, `justification`, `system_prompt`, `tools_json`, `focus_json`, `status` (`draft`/`approved`/`retired`), `version`, `origin` (`generated`/`user`), `ts` |
| `_AgentStep` | `id`, `stage`, `agent`, `kind` (`llm`/`tool`), `summary`, `payload_json`, `ms`, `ts` — the audit/stream trail |

Edges: `(_Session)-[:HAS_MESSAGE]->(_Message)`, `(_Message)-[:ANSWERS]->(_ChecklistItem)`,
`(_Brief)-[:DERIVED_FROM]->(_Message|_Attachment)`, `(_FormSpec)-[:FOR_BRIEF]->(_Brief)`,
`(_OntologySpec)-[:DERIVED_FROM]->(_Brief|_FormSpec|_Attachment)`,
`(_ExpertRole)-[:DERIVED_FROM]->(_Brief|_OntologySpec)`, `(_ExpertRole)-[:FOCUSES_ON]->(:_OntologyType)`,
and `(:_Provenance)` edges from every generated instance node back to the `_FormAnswer` or `_Attachment` it
came from (so "where did this number come from?" is answerable in the graph).

**Versioning and staleness.** `_Brief`, `_OntologySpec` and `_ExpertRole` are versioned, never overwritten.
When an upstream artifact gets a new version, every downstream artifact is flagged `stale=true` and must be
re-derived and re-approved. That is what makes "go back to stage 1 whenever you like" safe.

---

## 4. The four agents

All four follow the same contract: **one LLM call per turn, structured JSON output, state written to
FalkorDB before the response is returned, every step streamed.** The system prompts live in
`ripple/onboarding/agents/prompts/*.md` and are versioned in git.

### 4.1 Interviewer (stage 1)

* Persona: a product manager who is also a supply chain expert. Asks about the business first, then the
  physical/commercial chain: products → BOM/components → sourcing → manufacturing → movement → warehousing →
  distribution → customers → the commercial layer (contracts, SLAs, incoterms) → the pain that brought them here.
* **Dynamic checklist.** Internal only (never rendered to the user). Each turn's structured output is:
  ```json
  {"reply": "...", "checklist_ops": [{"op": "add|resolve|revise|drop", "id": "...", "question": "...", "why": "..."}],
   "brief_patch": {...}, "ask_for_files": ["..."], "done": false, "done_reason": ""}
  ```
  The checklist is the agent's working memory: it stops repetition, it makes the interview length scale with
  how complicated the business is, and `open` count is the progress signal the stage machine reads.
* **Start small:** the opening turn asks a handful of questions (3–5), not a wall. Depth comes from follow-ups.
* **Attachments:** the agent may ask for documents at any point; uploads are parsed (§5) and injected into its
  context as summaries + extracted tables, and recorded as `_Attachment` with provenance.
* **Termination:** the agent decides (`done: true` with a reason) when its checklist has no open items it
  judges material. A guard rail: the stage machine will not accept `done` while a *required* core topic in
  the brief schema is still empty — it reopens the checklist item instead.
* Output: `_Brief` v1 — a structured document (products, components, suppliers by type, sites, transport
  modes, markets, constraints, risks, vocabulary, open unknowns), shown to the user as a readable summary.

### 4.2 Data agent (stage 2)

* Reads the brief; decides which entities, which properties and which numbers are needed for the ontology to
  be more than a diagram.
* **Iterative in-chat forms.** It emits a `FormSpec` that renders as a form **inside the chat thread**. The
  user clicks any blank and fills it. On submit, the agent reads the answers and may emit another round —
  narrower, deeper, or asking about something the answers exposed. Rounds continue until the agent is
  satisfied (its own checklist again, stage-scoped).
* **Field types supported:** short text, long text, number (with unit), currency, percent, integer, date,
  date range, single select, multi select, boolean, geo/location, file, and **repeating group** (a table:
  "list your tier-1 suppliers: name, country, part, lead time, share of volume"), plus conditional visibility
  (`show_if`). Every field carries `label`, `help`, `placeholder`, `unit`, `required`, `example`.
* **Both modes of answering.** A field may be answered by typing a value, or by pointing at an uploaded file
  ("this column of suppliers.csv"). The agent proposes the mapping from a profile of the file (columns,
  dtypes, sample rows); the user confirms it.
* **Files.** The agent asks up front whether the user has data files; if so, uploads are profiled and the
  form shrinks to what the files do not already answer.
* **Never invent data.** When a number is unknown, the agent asks for a **ballpark** and records
  `confidence: "ballpark"`. It must not fill a value itself.
  **Exception, demo only:** a **Synthesize** button on each form calls a separate LLM pass that autofills the
  whole form with plausible values. Every value it writes is stored with `source: "synthetic"`, rendered with a
  visible synthetic badge, and the tenant is flagged `has_synthetic: true`. This is a demo affordance, never
  the agent's own behaviour.
* Output: the **Data Pack** — `_FormAnswer` rows + profiled `_Attachment`s.

### 4.3 Ontology agent (stage 3)

* Input: brief + data pack. Output: an **Ontology Spec** (JSON), the tenant's permanent graph model:
  ```json
  {"version": 1,
   "types": [{"label": "Supplier", "description": "...", "id_pattern": "SUP-####",
              "properties": [{"name": "lead_time_days", "type": "integer", "unit": "days", "required": false,
                              "description": "..."}],
              "tags": ["RiskBearing", "Party"], "display": {"icon": "...", "color": "...", "title_property": "name"}}],
   "relationships": [{"type": "SUPPLIES", "from": "Supplier", "to": "Part", "cardinality": "many-to-many",
                      "properties": [...], "description": "..."}],
   "indexes": [...], "rationale": "...", "coverage": {"unmapped_answers": [...], "assumed": [...]}}
  ```
* **Review and approval is mandatory.** The UI renders the spec as both a diagram (force graph of types and
  relationships) and an editable table. The user can rename types, change property types/units, add or drop
  relationships, and ask the agent in chat to change it ("merge Vendor and Supplier"). Approve commits
  `status: approved`.
* **On approval:** `graph/apply.py` creates indexes for the spec, then the loader writes the instance data —
  every form answer, every row of every mapped uploaded table — as nodes and edges of the approved types,
  with `_Provenance` edges back to their source and `source`/`confidence` carried onto the properties.
* Validation before anything is written: unique labels/relationship types, no reserved `_` prefix, every
  relationship endpoint resolves, property types are from the allowed set, id patterns unique per type.

### 4.4 Expert generator (stage 4)

* Input: brief + approved ontology. It is **free to invent roles** — no fixed menu — but every role must come
  with a **justification tied to the ontology**: which node/relationship types it covers, which real problems
  of this supply chain it exists to solve, and why that work does not belong to another role. A role with no
  ontology footprint is rejected at validation and the agent is asked to drop or merge it.
* For each role it writes: `name`, `title`, `mandate` (what it owns), `justification`, `focus` (the subgraph
  it reasons over), `playbook` (typical questions and the shape of a good answer), and the **full system
  prompt**, written to be executed as-is.
* **Approval is mandatory**, per role: approve, edit, reject, or ask for another. After onboarding, the
  Experts page is full CRUD — create a role by hand, edit any prompt, retire one, duplicate one.
* **Dual persistence:** the role is a `_ExpertRole` node in FalkorDB *and* a markdown file at
  `tenants/<tenant>/experts/<name>.md` (front-matter + prompt). The graph is the source of truth; the file is
  a readable export that can also be re-imported, so prompts can be reviewed in git or a text editor.
* **Each role is a real runtime agent.** `experts/runtime.py` runs any role through the standard tool loop
  with its own system prompt, the ontology spec injected, and its tool allow-list.
  **Open:** the tool set each role gets is decided with the main application (§10). M5 ships a minimal
  read-only set (ontology introspection, node lookup, neighbourhood, aggregate) so that a generated expert can
  be asked a question and answer it from the tenant's real graph — enough to prove the role is alive.

---

## 5. Attachments

* Native, no new dependency: `.csv`, `.tsv`, `.json`, `.jsonl`, `.md`, `.txt` (pandas is already pinned).
* `.xlsx`, `.pdf`, `.docx` need a decision: add `openpyxl`, `pypdf`, `python-docx` (small, pure-ish, easy to
  vendor) **or** route binary files through the Claude Code bridge, which can read them. Recommendation: add
  the three libraries — it keeps parsing deterministic and offline. Decide in M3.
* Every upload is stored under `tenants/<tenant>/uploads/`, hashed, and **profiled**: for tables, columns,
  dtypes, null rates, cardinality, min/max, 5 sample rows; for documents, a text extract plus an LLM summary.
  Only the profile and the summary go into agent context — never a whole 18 MB file.
* Uploads are untrusted input: parse them in isolation, never execute anything from them, and treat text
  inside them as data, not as instructions to the agents (the system prompts say so explicitly).

---

## 6. Stage machine, persistence, resume

* Stages: `interview → data → ontology → experts → ready`. The `_Session.stage` is the cursor.
* **Non-linear.** The user can jump to any stage they have already reached, from a stage rail in the UI or by
  just saying it in chat ("wait, go back — we also ship by rail"). The jump is a first-class event: the target
  stage's agent re-enters with its checklist restored, downstream artifacts are flagged stale, and the UI
  shows what will need re-approval.
* **Resume.** Every message, checklist operation, form, answer and agent step is written to FalkorDB as it
  happens. Reload mid-answer and the thread, the open form (with partial values) and the stage come back.
  An LLM call that was in flight when the browser closed is re-issued on resume, not lost.
* **Re-onboarding.** A tenant can run onboarding again later (new product line, new region). It starts from
  the existing brief and ontology rather than from zero, and produces new versions.
* **Streaming.** `onboarding/events.py` publishes every agent step; `GET /api/onboarding/stream` is an SSE
  endpoint; the UI shows the agents thinking, calling tools, and writing to the graph in real time.

---

## 7. API surface (first cut)

```
GET    /api/tenant                              current tenant + stage + staleness
POST   /api/onboarding/start                    create tenant + session
GET    /api/onboarding/session                  full resumable state (messages, open form, stage)
POST   /api/onboarding/message                  user turn -> runs the stage agent
POST   /api/onboarding/forms/{id}/answers       partial save (autosave per field)
POST   /api/onboarding/forms/{id}/submit        submit -> next agent round
POST   /api/onboarding/forms/{id}/synthesize    demo autofill (marks everything synthetic)
POST   /api/onboarding/attachments              upload (multipart) -> profile
POST   /api/onboarding/goto                     jump to a stage
GET    /api/onboarding/stream                   SSE of agent steps
GET    /api/ontology                            current spec (draft or approved) + diagram payload
PATCH  /api/ontology/draft                      user edits to the draft
POST   /api/ontology/approve                    validate, apply schema, load instance data
GET    /api/experts                             list
POST   /api/experts                             create (user-authored)
PATCH  /api/experts/{id}                        edit (incl. system prompt)
POST   /api/experts/{id}/approve | /retire
POST   /api/experts/{id}/ask                    run that expert against the tenant graph
```

---

## 8. Testing without fakes

No scripted agents, no `FakeLLM`, no replayed transcripts. The suite is in two halves:

1. **Deterministic (`pytest -q`, default, no network, no LLM)** — everything that is not an LLM call:
   the onboarding store (write/read/resume), stage machine and staleness propagation, FormSpec validation and
   answer coercion for every field type, attachment profiling, OntologySpec validation, schema application,
   instance loading + provenance, expert store CRUD and file export/import round-trip, API routes driven with
   agent calls patched out at the **provider boundary** (a stub `LLMClient` that returns a fixed structured
   payload — this is a transport stub for route tests, not a fake agent).
2. **Live (`pytest -m llm`)** — real Claude Code calls, run on demand:
   * every system prompt returns output that validates against its schema, three runs each;
   * a full onboarding of a scripted *persona* (a shoe manufacturer, answers supplied by a second LLM
     playing the user) end to end: interview terminates, forms are coherent, ontology validates and loads,
     experts are generated with ontology-grounded justifications;
   * each generated expert answers one question from the loaded graph without hallucinating a node id.
   Transcripts are written to `artifacts/llm_runs/<ts>/` for inspection. Quality is judged by a rubric
   checklist in `eval/rubric.md`, scored by hand plus an LLM judge — recorded, never faked.

---

## 9. Milestones

Each ends with tests green and a commit.

| M | Title | Done when |
|---|---|---|
| **M0** | **Strip and scaffold** | `v1-dataco` tag pushed; DataCo ingest/scenarios/eval/static ontology/scripted agents/v1 UI pages removed; `ripple/llm/` provider layer in place (Claude Code default, OpenRouter selectable, no fakes); app boots to an empty tenant; suite green |
| **M1** | **Onboarding spine** | Platform labels + store + stage machine + SSE; `/api/onboarding/*` chat loop with a placeholder agent; UI chat page with stage rail; close the browser mid-thread and resume exactly |
| **M2** | **Interviewer** | Real agent, dynamic internal checklist, brief schema + patching, attachment intake and profiling, agent-decided termination with the core-topic guard; live test: shoe-manufacturer persona yields a coherent brief |
| **M3** | **Data agent + in-chat forms** | FormSpec model + all field types + repeating groups + conditionals; inline form renderer with per-field autosave; file→field mapping; multi-round loop; Synthesize button with synthetic badging; ballpark/confidence capture |
| **M4** | **Ontology agent** | Spec generation + validation; review UI (diagram + editable table + chat edits); approve → indexes applied → instance data loaded with provenance; "where did this number come from" answerable in Cypher |
| **M5** | **Expert generator + runtime** | Roles generated with ontology-grounded justification; per-role approve/edit/reject; CRUD page; graph + markdown dual persistence with round-trip; `ExpertAgent` answers a real question from the tenant graph with the minimal read-only tool set |
| **M6** | **Non-linearity, versioning, re-onboarding** | Jump back from any stage; staleness propagation and re-approval flow; artifact version history visible; re-run onboarding on an existing tenant |
| **M7** | **Hardening and docs** | Live-LLM suite + rubric run and recorded; generated README/ontology docs; Docker + bridge path verified end to end; `docs/KNOWN_ISSUES.md` current |
| **M8** | **Main application** | Gated on §10 — not started until the workflow is specified |

### 9.1 Open decisions

1. **Queries against a generated ontology (deferred at your request).** `CLAUDE.md` says every product query
   lives in `graph/queries/*.cypher`, which assumed fixed labels. With a per-tenant ontology the options are
   (a) a fixed **base-concept layer** the generated types are mapped onto, so hand-written queries keep
   working; (b) **templated** queries rendered per tenant from the spec; (c) agents **write Cypher at runtime**
   against the injected spec, validated before execution. This only has to be settled when the main
   application needs real analytics — i.e. before M8, and it shapes M5's tool set. **To be decided with you.**
2. **Binary attachment parsing** — add `openpyxl`/`pypdf`/`python-docx`, or route through the bridge (M3).
3. **Identity.** There is no auth today. One user = one tenant; the plan assumes a single local user and a
   tenant id in a cookie. If this is ever multi-user, that changes M1.

---

## 10. Out of scope until specified

The post-onboarding application — what the control tower looks like on a generated ontology, how experts are
orchestrated, how disruptions/incidents/actions/memory work now that nothing is DataCo-shaped, and which tools
each expert gets. v1's code for these is archived, not reused. The plan picks up at M8 once you describe it.
