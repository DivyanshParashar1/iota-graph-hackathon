# Ripple v2 — Feature Summary

A plain-language read of where the product is today and what it becomes. Build sequence: `plan.md`.

---

## The shift in one sentence

Today Ripple is a supply chain control tower that only works on one dataset; v2 turns it into a product that
**interviews any company and builds their supply chain brain from scratch** — their ontology, their data,
their expert agents.

---

## Where it stands today (v1, shipped)

| Area | Today |
|---|---|
| Data | One public dataset (DataCo) plus committed synthetic suppliers/parts/ports/lanes |
| Ontology | Hand-written in Python (`ripple/ontology.py`); identical for every user |
| Agents | Four fixed agents (sentinel, analyst, planner, comms), scripted by default, LLM optional |
| Queries | ~30 hand-written Cypher files that assume DataCo's labels |
| UI | Control tower, incident timeline, actions, company brain, memory |
| Onboarding | None — the app arrives pre-filled |
| Verdict | A strong demo of one supply chain. Not a product anyone else can use. |

**All of it is archived at git tag `v1-dataco` and removed from `main`.** The useful bones survive: FalkorDB
access with tenant isolation, the named-query loader, the FastAPI/React shell, the Claude Code and OpenRouter
LLM clients, the graph and map views.

---

## What v2 adds

### 1. A first-run experience that is a conversation, not a config screen

The user lands in a chat with a **product manager who is also a supply chain expert**. It asks about the
business, then works outward through the chain — products, components, sourcing, manufacturing, movement,
distribution, customers, contracts, and the pain that brought them here.

* It starts with a handful of questions and goes deeper only where the answers warrant it.
* Behind the scenes it keeps a **living checklist of its own open doubts** — items get added as new ground
  opens up and resolved as they are answered. The user never sees it; its job is to stop the agent repeating
  itself, keep questions short, and make the interview as long as the business is complicated, no longer.
* The user can **attach any document they already have** — supplier lists, BOMs, contracts, spreadsheets —
  and the interview adapts around what the files already say.
* The agent decides when it is done, and produces a structured **Supply Chain Brief** the user can read.

### 2. A data agent that asks for the numbers, in forms, in the chat

The brief says *what the chain is*; this stage makes it concrete. The data agent works out exactly which
entities, properties and numbers it needs — for a shoe maker: where the leather comes from, how many tanneries,
lead times, order volumes, which plants cut and which stitch — and asks for them as a **form rendered inside
the chat**. The user clicks any blank and fills it.

* **Iterative:** submit a form, and the agent reads it and may come back with a sharper round. It stops when
  it has what the ontology needs.
* **Every field type:** text, numbers with units, currency, percentages, dates and ranges, single and multi
  select, yes/no, locations, file pickers, and **repeating tables** ("list your tier-1 suppliers") — with
  fields that appear only when they become relevant.
* **Type it or point at a file.** Upload a CSV and the agent proposes which column answers which field; the
  user confirms.
* **Nothing is invented.** If a number is unknown the agent asks for a **ballpark** and records it as one.
* **Synthesize button (demo only):** one click autofills a whole form with plausible values so the product can
  be demoed without a real company. Every synthetic value is badged in the UI and tagged in the graph, and the
  agent itself will never do this on its own.

### 3. An ontology built for that company, stored in FalkorDB

An ontology agent reads the brief and the data and designs **this tenant's graph model**: node types with
descriptions and identifier patterns, properties with real types and units, relationships with direction and
cardinality — plus its reasoning, and an honest list of what it had to assume.

* The user **reviews it as a diagram and as an editable table**, renames things, fixes types, adds or removes
  relationships, or just asks in chat for a change. **Nothing is committed without approval.**
* On approval the schema is applied to FalkorDB and the collected data is **loaded as real nodes and edges**,
  with every value carrying a trail back to the form answer or file it came from — so "where did this number
  come from?" is a question the graph itself can answer.
* The ontology is generated per tenant, then **fixed for that tenant** — versioned, and re-derived if the user
  goes back and changes the brief.

### 4. Expert agents invented for that supply chain

A generator agent decides which **expert roles** this particular chain needs and writes them. Ocean freight in
the picture → a logistics expert who knows reroutes, transit times and carrier risk. Food or pharma → a
compliance and cold-chain expert. Single-source components → a sourcing and resilience expert.

* Roles are **invented, not picked from a menu** — but each must justify itself against the ontology: which
  types it covers, which real problems it solves, why it isn't someone else's job. Unjustified roles get
  rejected and merged.
* For each role the agent writes the full **system prompt**, mandate, focus area and playbook.
* **The user approves each one** — accept, edit, reject, or ask for another.
* They are **real runtime agents**, not personas: own system prompt, own tool access, reading the tenant's
  ontology and data. After onboarding there is an Experts page with **full CRUD** — write your own role, edit
  any prompt, retire one.
* Each role lives both as a node in FalkorDB and as a readable markdown file under `tenants/<tenant>/experts/`,
  so prompts can be reviewed in git or a text editor.

### 5. The experience around all of it

* **Nothing is lost.** Every message, checklist move, form, answer and agent step is written to FalkorDB as it
  happens. Close the browser mid-sentence; come back to the same thread, the same half-filled form, the same
  stage.
* **Go back at any time.** The four stages are not a wizard. Say "actually, we also ship by rail" during
  ontology review and you're back in the interview; everything downstream is marked as needing a re-look
  rather than silently rewritten. Artifacts are versioned, never overwritten.
* **Watch it work.** The agents' steps stream live — questions forming, forms being drafted, the ontology
  being written into the graph.
* **Run it again later.** New product line, new region, new supplier tier: re-run onboarding on an existing
  tenant and it extends what's there instead of starting over.
* **One user, one tenant**, isolated in its own FalkorDB graphs, exactly as the tenant scoping already enforces.

### 6. Under the hood

* **FalkorDB is the whole backbone** — onboarding state, the generated ontology, the company's data, the
  expert roles, the provenance trail, agent memory.
* **Real LLM calls only.** Scripted agent modes and fake clients are gone. The default provider is the
  **Claude Code bridge** (runs on the local `claude` login, no API key); **OpenRouter** stays available.
* **Testing without fakes:** deterministic tests cover everything that isn't a model call; a live suite drives
  a full onboarding with a second model playing a shoe manufacturer, and keeps the transcripts.

---

## What is not decided yet

* **The main application** — what the user sees once onboarding is done, how the experts are orchestrated, and
  how incidents, actions and memory work on a generated ontology. Spec pending; the plan leaves it as the last
  milestone.
* **How analytical queries work against a per-tenant ontology** — fixed base concepts the generated types map
  onto, per-tenant query templates, or agents writing validated Cypher at runtime. This one has to be settled
  before the main application is built.
* **Parsing of Excel/PDF/Word uploads** — add three small libraries, or hand those files to the Claude Code
  bridge to read.
