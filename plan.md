# Ripple: Build Plan for a Single Autonomous Session

This plan turns `idea.md` (the product spec) into working code in **one uninterrupted Claude Code cloud session**.
`idea.md` says *what* and *why*. This file says *how*, *in what order*, and *how to know each step is done*.
When the two disagree, this file wins. When this file disagrees with `reference/FALKORDB_VERIFIED.md`, that file wins.

---

## 0. Read this first: rules for the build session

1. **No external services exist.** There is no FalkorDB server, no Docker, no API keys, and possibly no network.
   Everything must run and be tested with:
   * **Embedded FalkorDB** (`falkordblite`): a real FalkorDB engine started in-process from a `.db` file.
     It runs the same Cypher, indexes and algorithms as the server.
   * **Scripted agents**: deterministic agent logic that calls the same MCP tools an LLM would. LLM mode
     (Claude via the `anthropic` SDK) is implemented too, but is only exercised in tests through a fake client.
   * **Hash embeddings**: a deterministic local 384-d embedder. OpenAI embeddings are optional.
   The cloud VM is Ubuntu 24.04 x86_64 (4 vCPU, 16 GB RAM), Python 3.12, Node 22. The offline setup was tested
   on exactly that platform with networking disabled: 40 s, all smoke checks green, UI builds.
   **Optional bonus:** the cloud VM also has Docker. If `docker run -d -p 6379:6379 falkordb/falkordb:latest`
   works (needs Docker Hub access), run the test suite once more with `RIPPLE_DB_MODE=remote` to prove the
   remote path. If it doesn't work, skip it; it's not required.
2. **Set up first:** run `bash scripts/setup_env.sh`. It installs Python deps from `vendor/wheels` and UI deps
   from `vendor/npm-cache` offline, then runs `scripts/verify_falkordb.py`. A SessionStart hook in
   `.claude/settings.json` runs it automatically in cloud sessions. If it already ran, `.venv/` exists.
   Always use `.venv/bin/python` and `.venv/bin/pytest`.
3. **Do not add dependencies.** Everything needed is pinned in `requirements.lock` (Python) and
   `ui/package-lock.json` (UI) and vendored. If something seems missing, use the standard library or write it.
   If you really need a new package and the network works, add it to `pyproject.toml`, re-lock, and say so in the
   final report.
4. **Verified syntax only.** Before writing Cypher, read `reference/FALKORDB_VERIFIED.md`. Key traps:
   vector `score` is a distance (sort ASC); map properties are illegal (store JSON strings);
   `MATCH p=shortestPath(...)` is illegal (use `WITH shortestPath(...) AS p` or `algo.SPpaths`);
   `EXISTS { }` subqueries are illegal; `CREATE INDEX` on an existing index raises (catch it).
5. **One process owns the DB file.** Never open the same embedded `.db` from two processes. Tests use a fresh temp
   path per test session.
6. **Work milestone by milestone (Section 9).** Each milestone ends with its tests green, then a git commit
   (`git add -A && git commit -m "M<n>: ..."`). Don't start the next milestone with red tests. If you are stuck
   on one item for a long time, record it in `docs/KNOWN_ISSUES.md`, take the documented fallback, and move on.
7. **Never fabricate results.** Numbers in the README (counts, latencies, eval scores) come from running
   `scripts/report_numbers.py`, not from guesses.
8. Keep every Cypher query the product uses in `graph/queries/*.cypher` and load it from there
   (`ripple/graph/queries.py`). The README's query section is generated from those files, so code and docs
   can't drift apart.

---

## 1. What is already in the repo

| Path | Contents |
|---|---|
| `idea.md` | Product spec (hackathon facts, ontology, agents, tools, queries, memory, brain, UI, eval) |
| `plan.md` | This file |
| `CLAUDE.md` | Short standing rules for any Claude session in this repo |
| `pyproject.toml`, `requirements.lock` | Python 3.12/3.13 deps, pinned (117 packages) |
| `vendor/wheels/` | Linux x86_64 wheels for cp312 + cp313 plus pure-Python wheels, for offline install |
| `vendor/npm-cache/` | npm cache with every tarball in `ui/package-lock.json` (Linux x64 native binaries included) |
| `ui/` | Vite 7 + React 19 + TypeScript + Tailwind 4 skeleton that builds (`npm run build`); deps: react-router-dom, react-force-graph-2d, leaflet, react-leaflet |
| `data/raw/DataCoSupplyChainDataset.csv.gz` | DataCo dataset (18 MB gz, latin-1). See `data/raw/README.md` for the measured profile |
| `scripts/setup_env.sh` | Offline-first installer |
| `scripts/verify_falkordb.py` | 17 checks of the FalkorDB features we depend on |
| `reference/` | Offline docs: FalkorDB (Cypher, algorithms, vector index, Graphiti), Anthropic Python SDK, verified-syntax notes |
| `.env.example` | All config knobs |

Measured facts that correct `idea.md`:

* DataCo order dates run **2015-01-01 to 2018-01-31** (not 2019). The CSV is **latin-1**.
* 118 products, 65,752 orders, 180,519 items, 20,652 customers, 23 regions, 5 markets.
* Open orders (statuses PENDING, PROCESSING, PENDING_PAYMENT, ON_HOLD, PAYMENT_REVIEW): 33,932 orders,
  $19.1M in item sales.
* Embeddings default to **384-d** (local hash embedder), not 1536.

---

## 2. Target architecture (as built)

```
ripple/                         # Python package (installed editable by setup_env.sh)
  config.py                     # pydantic-settings; reads .env
  db.py                         # get_db(): embedded or remote FalkorDB; TenantScope; save()
  graph/
    schema.py                   # applies graph/schema.cypher idempotently, per graph
    queries.py                  # loads graph/queries/*.cypher by name: Q("blast_radius_port")
  embed.py                      # HashEmbedder(384) + optional OpenAIEmbedder; same interface
  ingest/
    dataco.py                   # CSV.gz -> Orders, OrderLines, Products, Customers, Markets (PII dropped)
    synth.py                    # deterministic generator -> data/synthetic/<tenant>/*.json|csv|md
    load_synth.py               # synthetic files -> graph
    docs.py                     # contracts/SOPs/postmortems/chats -> Document/Chunk/Thread/Message + MENTIONS + Decision
    delta.py                    # incremental ingest of new chats/docs (owner handover)
    build.py                    # one command: build a tenant end to end (python -m ripple.ingest.build --tenant dataco)
  tools/                        # pure functions: (scope, **args) -> ToolResult. The MCP server wraps these.
    base.py                     # ToolResult{data, node_ids, edges, cypher_ids}, ToolCall logging
    impact.py                   # match_event_to_entities, blast_radius, revenue_at_risk, customer_exposure, late_risk_baseline
    algos.py                    # single_points_of_failure, supplier_influence, supplier_clusters, alt_route
    sourcing.py                 # alt_suppliers, contract_terms
    actions.py                  # open_incident, propose_action, approve_action, reject_action, execute_action, undo_action, draft_notification
    brain.py                    # who_owns, who_knows, trace_decision, doc_search, ask (router)
    memory.py                   # record_episode, recall_similar_episodes, get_playbook, upsert_fact, facts_about, conversation log
    registry.py                 # TOOLS: name -> (fn, json schema, read/write, description)
  mcp_server.py                 # FastMCP server exposing the registry; tenant from session, never from args
  agents/
    state.py                    # IncidentState TypedDict {tenant_id, incident_id, mode}
    sentinel.py analyst.py planner.py comms.py
    llm.py                      # Claude tool-use loop over registry tools + ID validator; FakeLLM for tests
    orchestrator.py             # LangGraph StateGraph: sentinel -> (analyst || comms_prefetch) -> planner -> comms -> close
    events.py                   # in-process pub/sub of agent steps for SSE
  api/
    app.py                      # FastAPI app factory; serves ui/dist in prod
    routes_*.py                 # incidents, actions, brain, memory, ontology, scenarios, tenants
graph/
  schema.cypher                 # indexes (one statement per line)
  queries/*.cypher              # every product query, with a header comment: name, purpose, params
  ontology.md                   # generated from ripple/ontology.py
data/
  raw/                          # DataCo (committed gz)
  synthetic/dataco/, synthetic/nova/   # generated, committed (judges can inspect)
  scenarios/*.yaml              # 4 scenarios + ground truth file references
eval/
  ground_truth.py               # pandas-only computation of expected impact (never touches the graph)
  run_scenarios.py              # agents vs ground truth, prints a table, exits non-zero on mismatch
  brain_questions.yaml          # 20 questions with expected source doc ids
  run_brain_eval.py
  load_test.py                  # 20 concurrent sessions over 2 tenants
tests/                          # pytest; see Section 8
scripts/
  setup_env.sh  verify_falkordb.py  report_numbers.py  demo.py (CLI walkthrough of the 3 demo acts)
ui/                             # Vite React app (Section 7)
Dockerfile, docker-compose.yml, render.yaml   # deploy (written, not runnable in the cloud session)
README.md, AI_DISCLOSURE.md, docs/blog.md, docs/KNOWN_ISSUES.md, LICENSE (MIT)
```

### 2.1 Key design decisions (keep them)

| Decision | Why |
|---|---|
| Tools are plain Python functions taking a `TenantScope`; MCP, agents, API and tests all call the same functions | One implementation, testable without an MCP transport |
| `TenantScope(tenant_id)` exposes only `.ops` (`tenant_<id>`) and `.mem` (`mem_<id>`) graphs and raises on any other name | Isolation is enforced in code, not prompts (Track 2) |
| Every `ToolResult` carries `node_ids` and `edges` (`[src_id, REL, dst_id]`) | Path highlighting in UI; ID validator for LLM answers |
| Every node has a string `id` with a type prefix (`SUP-T2-0042`, `PRT-0103`, `PRD-1360`, `ORD-77202`, `OL-180517`, `CUS-11599`, `PORT-CNSHA`, `LANE-CNSHA-USLAX-STD`, `INC-...`, `ACT-...`) | Unambiguous IDs across labels; deterministic IDs make MERGE idempotent |
| Incident / Action / Episode IDs are deterministic hashes of their inputs (`INC-` + sha1(tenant, disruption_id)[:10]; `ACT-` + sha1(incident, type, sorted params)[:10]) | Re-running an agent or a concurrent duplicate request can't create duplicates |
| Maps are stored as JSON strings (`params_json`, `payload_json`) | FalkorDB rejects map properties |
| Agents have two modes: `scripted` (default, deterministic) and `llm` (Claude tool use) | Works with no key; demo is reliable; LLM mode shows dynamic tool selection |
| The ground truth for scenarios is computed with pandas from the source files, never from the graph | A real correctness check of the graph queries |
| The API process owns the embedded DB; the UI talks only to the API | Embedded DB is single-process |

---

## 3. Data model (implementation details beyond idea.md Section 5)

Use the labels and relationships in `idea.md` §5.2–5.3 with these specifics.

### 3.1 Graph keys

`tenant_dataco`, `mem_dataco`, `tenant_nova`, `mem_nova`. `ToolCall`, `Incident`, `Action`, `Agent`, `Disruption`,
and `Decision` live in the **ops** graph (they link to ops entities). `Episode`, `Fact`, `Playbook`, `User`,
`Conversation`, `Message`(chat-with-Ripple) live in the **mem** graph and refer to ops nodes by id strings
(cross-graph edges don't exist).

Name clash: company chat messages (Slack-style, ops graph) use label `ChatMessage`; conversation-with-Ripple
messages (mem graph) use `ConvMessage`. Update `idea.md`-style docs accordingly.

### 3.2 Mapping DataCo onto the ontology

| Graph | From DataCo |
|---|---|
| `Order {id:'ORD-'+Order Id, date, status, region(stripped), market, country, city, total (sum of Sales over items), profit (Order Profit Per Order summed), late_risk (max Late_delivery_risk), delivery_status, days_real, days_sched, shipping_mode, open (status in OPEN_STATUSES)}` | Group items by `Order Id` |
| `OrderLine {id:'OL-'+Order Item Id, qty, total (Sales), price}` | One per row |
| `Product {id:'PRD-'+Product Card Id, name, category, department, price}` | Distinct products |
| `Customer {id:'CUS-'+Order Customer Id, segment, city, state, country}` | No names, emails, streets, zips, passwords |
| `Market {name}`, `Region {name}` | `(Order)-[:IN_MARKET]->(Market)`, `(Region)-[:PART_OF]->(Market)`, `(Order)-[:IN_REGION]->(Region)` |
| `SHIPS_VIA` | Each order is assigned a Lane deterministically (Section 3.3) |

Use `Sales` for revenue, not `Order Item Total` (the latter is after discount; pick one, document it, and use the
same in `eval/ground_truth.py`). Recommended: **revenue = sum(Sales)**.

### 3.3 Synthetic layer generator (`ripple/ingest/synth.py`, `seed=42` for dataco, `seed=7` for nova)

The generator writes plain files under `data/synthetic/<tenant>/` (`suppliers.csv`, `parts.csv`, `bom.csv`,
`supplies.csv`, `supplies_to.csv`, `qualified.csv`, `ports.csv`, `lanes.csv`, `plants.csv`, `product_plant.csv`,
`order_lane.csv`, `employees.csv`, `teams.csv`, `ownership.csv`, `contracts.csv`, `docs/**/*.md`, `chats/*.json`,
`decisions.json`, `planted.json`). Loaders read only these files, and `eval/ground_truth.py` reads the same files
with pandas. Use `random.Random(seed)` and `Faker` seeded with the same seed; never rely on dict/set ordering.
Generated files are committed.

Volumes (dataco; nova is ~10%):

| Layer | Rule |
|---|---|
| Ports (25, real names and coordinates, UN/LOCODE-style ids) | CNSHA Shanghai, CNNGB Ningbo, CNSZX Shenzhen/Yantian, CNTAO Qingdao, HKHKG Hong Kong, SGSIN Singapore, KRPUS Busan, TWKHH Kaohsiung, VNSGN Ho Chi Minh, MYPKG Port Klang, INNSA Nhava Sheva/JNPT, AEJEA Jebel Ali, NLRTM Rotterdam, BEANR Antwerp, DEHAM Hamburg, ESVLC Valencia, GBFXT Felixstowe, USLAX Los Angeles, USLGB Long Beach, USNYC New York/NJ, USSAV Savannah, BRSSZ Santos, MXZLO Manzanillo, PAONX Colón, ZADUR Durban |
| Plants (12) | Each at a supply-side port country (CN×4, VN, IN, MY, TW, KR, MX, TR→use nearest port, US). `(Plant)-[:NEAR]->(Port)` |
| Product → Plant | Each of the 118 products `MADE_AT` exactly one plant, weighted toward CN/VN/IN; record in `product_plant.csv` |
| Destination port per region | Fixed table mapping each of the 23 Order Regions to a destination port (e.g. Western Europe → NLRTM, Central America → MXZLO, South America → BRSSZ, West of USA → USLAX, East of USA → USNYC, Oceania → a port you add or SGSIN, etc.) |
| Lanes (~120) | `LANE-<orig>-<dest>-<mode>` for every (plant port, destination port, shipping mode) combination actually used, plus extra port-to-port lanes. `transit_days` from great-circle distance / 600 km/day (sea) with mode multipliers: Standard 1.0, Second 0.8, First 0.6, Same Day 0.4 (air). `carrier` from a fixed list of 6 synthetic carriers |
| Order → Lane | An order's lane = (plant port of its first product line, destination port of its region, its shipping mode). Write `order_lane.csv`. This makes a port closure hit orders through real product→plant→port structure |
| `(Port)-[:CONNECTS {transit_days}]->(Port)` | Materialize from lanes (both directions, min transit_days per pair) for routing |
| Suppliers (tier1 150 / tier2 300 / tier3 200) | Name `"<Faker company> [SYNTH]"`, country weighted (CN 35%, VN 10%, IN 10%, TW 7%, KR 6%, MY 5%, MX 6%, US 8%, DE 5%, TR 4%, BR 4%), `SHIPS_FROM` the nearest port in its country (or region), `reliability` 0.6–0.99, `capacity`, `risk_score` |
| Parts (~600) | 3–8 parts per product by department (Apparel: fabric, zipper, thread, label, dye; Footwear: sole, upper, laces, eyelets; Golf: shaft, grip, head; Technology/Fitness: PCB, battery, casing, display, sensor; etc.). Parts are shared across products in the same department. `(Part)-[:COMPONENT_OF {qty}]->(Product)` |
| `SUPPLIES` (~3,000) | Tier-1 → Part with `lead_time_days`, `unit_cost`, `share` (shares per part sum to 1.0). **20% of parts single-sourced** |
| `SUPPLIES_TO` (~800) | tier3 → tier2 → tier1 |
| `QUALIFIED_FOR` (~400) | Inactive alternates; at least 2 alternates **outside China** for every part that a scenario disrupts |
| **Planted chokepoints (3)** | Three tier-2 suppliers through which many tier-3 → tier-1 paths must pass (each receives from ≥15 tier-3 and feeds ≥20 tier-1, and those tier-3s have no other outlet). Record their ids in `planted.json`. Test: all 3 in top 5 of `algo.betweenness` over `Supplier`/`SUPPLIES_TO` |
| Employees (40) / Teams (6) | Synthetic names tagged `[SYNTH]`, emails `@ripple-demo.example`. `MEMBER_OF` |
| `OWNS_RELATIONSHIP` | Every tier-1 supplier has one current owner (`valid_from`, `valid_to=null`); ~30 suppliers also have a past owner with a closed window |
| Contracts (60) | One per major tier-1 supplier: `sla_days`, `penalty_pct`, `force_majeure` (bool + text), `exclusivity`. Rendered to markdown docs with numbered clauses |
| SOPs (15), postmortems (4), chats (30) | Template-generated markdown/JSON. Postmortems and chats contain explicit decisions. Each doc has YAML front matter: `id`, `type`, `title`, `authors` (employee ids), `mentions` (entity ids), `decisions` (list of `{id, summary, about: [ids], decided_at}`) |
| Hero entities (fixed names, used by the demo and eval) | `Shenzhen Volt Components [SYNTH]` (tier-1, CN, sole supplier of `Li-ion battery pack`); the 2024 Shenzhen typhoon postmortem that led to dual-sourcing the battery pack; a chat thread where the dual-sourcing was argued; an owner-handover chat used by the delta-ingest demo |

Nova (second tenant): different seed, own suppliers, its own ~12 synthetic products and ~3,000 synthetic orders
(no DataCo rows), different employee names. No id may collide with dataco ids: prefix nova ids with `N` after the
type (e.g. `SUP-N-...`, `ORD-N-...`).

### 3.4 Documents, chunks, entity linking, decisions (`ripple/ingest/docs.py`)

* `Document {id, type: contract|sop|postmortem|chat_thread, title, uri: 'data/synthetic/<t>/docs/...md', version, updated_at}`.
* Chunk by paragraphs to ~120–200 words with one-paragraph overlap. `Chunk {id: '<doc>#<n>', text, ordinal, embedding}`.
* Chats: `Thread {id, channel}` with `ChatMessage {id, ts, text, embedding}` and `(:Employee)-[:POSTED]->(:ChatMessage)`,
  `(:Thread)-[:HAS_MSG]->(:ChatMessage)`, plus a `Document` for the thread (type `chat_thread`) so citations are uniform.
* Entity linking: exact match on entity ids and names (case-insensitive, `[SYNTH]` suffix optional) from an
  in-memory dictionary of suppliers, parts, ports, products, employees → `MENTIONS {confidence: 1.0}`. Front-matter
  `mentions` also become MENTIONS edges (confidence 1.0). Fuzzy matches (token overlap ≥0.8) get confidence 0.7.
* Decisions come from front matter (the generator is the source of truth): `Decision {id, summary, decided_at, status}`
  with `SOURCED_FROM` → the Document and any ChatMessage ids listed, `ABOUT` → entities, and
  `(:Employee)-[:PARTICIPATED_IN]->(:Decision)` for authors. (LLM-based extraction is a stretch; not needed.)
* `AUTHORED`: Employee → Document from front matter.

### 3.5 Memory graph (`mem_<tenant>`)

| Label | Properties |
|---|---|
| `Episode` | `id, incident_id, disruption_type, entity_ids[], countries[], actions_taken[], outcome ('resolved'|'partial'|'failed'), revenue_before, revenue_after, summary, embedding, ts` |
| `Playbook` | `id, disruption_type, name, steps[] (action types in order), uses, successes, success_rate` ; `(:Episode)-[:USED]->(:Playbook)` |
| `Fact` | `id, subject_id, predicate, object, valid_at, invalid_at (null = current), source, confidence` ; `(:Fact)-[:SUPERSEDES]->(:Fact)` |
| `User`, `Conversation`, `ConvMessage` | `(:User)-[:HAD]->(:Conversation)-[:HAS_MSG]->(:ConvMessage {role, text, ts, sources_json})` |

Seed each tenant's mem graph with **3 playbooks** (port_closure, supplier_failure, carrier_strike) and **2 past
episodes** taken from the postmortems, so the first incident already has something to recall.

`recall_similar_episodes`: score = 0.5·[same disruption_type] + 0.3·Jaccard(entity_ids ∪ countries) +
0.2·(1 − vector distance of summaries). Return top 3 with the score breakdown.

Graphiti (`RIPPLE_GRAPHITI=1`): optional adapter `ripple/tools/graphiti_adapter.py` that mirrors Episodes into a
Graphiti graph via `FalkorDriver`. Needs an LLM key, so it's off by default and only import-tested. Do this last,
or skip it and say so in the README.

---

## 4. Tools (Section 8 of idea.md, made concrete)

All tools live in `ripple/tools/*.py` with signature `fn(scope: TenantScope, **args) -> ToolResult` and are
registered in `ripple/tools/registry.py` with a JSON schema, `kind` (`read|algo|write|memory`) and a one-line
description (these descriptions are what Claude sees, so make them good).

```python
@dataclass
class ToolResult:
    data: dict | list          # JSON-serializable payload
    node_ids: list[str]        # every node id the answer depends on
    edges: list[tuple[str, str, str]]  # (src_id, REL_TYPE, dst_id) for path highlighting
    queries: list[str]         # names of graph/queries/*.cypher used
    ms: float
```

Each call writes `(:ToolCall {id, tool, agent, args_json, ms, ts, n_nodes})` and, if inside an incident,
`(:Incident)-[:HAS_CALL]->(:ToolCall)`. Use a `logged_tool` decorator.

Required tools and their query files (name the `.cypher` files exactly like this):

| Tool | Query file(s) | Notes |
|---|---|---|
| `match_event_to_entities(event)` | `match_port_by_name.cypher`, `match_supplier_by_name.cypher`, `match_near_point.cypher` | event = {type, target_name or target_id, lat?, lon?, radius_km?}. Geo match in Python using haversine over Port/Supplier coordinates |
| `create_disruption(event)` | `create_disruption.cypher` | `Disruption {id, type, severity, started_at, expected_days, source, active:true}` + `AFFECTS` |
| `open_incident(disruption_id)` | `open_incident.cypher` | MERGE by deterministic id |
| `blast_radius(disruption_id, max_hops=6)` | `blast_radius_port.cypher` (Q1), `blast_radius_supplier.cypher` (Q2), `blast_radius_carrier.cypher` | Dispatch on what the disruption AFFECTS. Returns orders, revenue, customers, products, parts, suppliers, lanes, plus a capped (≤200 nodes) highlight subgraph with edges. Also writes `IMPACTS {revenue}` from Incident to the top-N orders and sets `Incident.revenue_at_risk/orders_at_risk/customers_affected` |
| `revenue_at_risk(incident_id)` | `revenue_at_risk.cypher` | Sum over open orders currently impacted, **recomputed live** (respects reroutes and supplier switches) |
| `customer_exposure(incident_id, top_k)` | `customer_exposure.cypher` | Top customers/segments by revenue at risk |
| `late_risk_baseline(mode, market)` | `late_risk_baseline.cypher` (Q5) | Must equal the pandas aggregate |
| `single_points_of_failure(top_k)` | `betweenness_suppliers.cypher` + `single_sourced_parts.cypher` (Q3) | Combine both signals |
| `supplier_influence(top_k)` | `pagerank_suppliers.cypher` | |
| `supplier_clusters()` | `wcc_suppliers.cypher`, `cdlp_suppliers.cypher` | Group sizes + countries per cluster |
| `alt_suppliers(part_id, exclude_country)` | `alt_suppliers.cypher` (Q4) | Excludes suppliers affected by an active disruption |
| `alt_route(origin_port, dest_port, avoid_ports)` | `alt_route.cypher` (algo.SPpaths over CONNECTS, filtered) | Fallback `alt_route_unweighted.cypher` (`WITH shortestPath`) |
| `contract_terms(supplier_id, clause)` | `contract_for_supplier.cypher` + vector search scoped to that contract's chunks | Returns clause text + penalty math for this incident |
| `who_owns(entity_id, at=None)` | `who_owns.cypher` (Q6) | Temporal |
| `who_knows(topic_or_entity)` | `who_knows.cypher` | Rank employees by AUTHORED/POSTED/PARTICIPATED_IN on docs/decisions that MENTION or are ABOUT the entity (or match the topic via doc_search) |
| `trace_decision(entity_id or question)` | `trace_decision.cypher` (Q7) | Decision → sources → people |
| `doc_search(query, entity_scope=None, k=8)` | `doc_search.cypher` (Q8) | Vector + graph expansion; optional scope filter to chunks that MENTION entities in scope |
| `propose_action(incident_id, type, params, evidence_ids, agent)` | `propose_action.cypher` (+ `BASED_ON` per evidence id with `role`) | Validates evidence ids exist |
| `approve_action / reject_action(action_id, user)` | `approve_action.cypher` | `APPROVED_BY` → `User` node in ops graph |
| `execute_action(action_id)` | one file per action type: `exec_reroute.cypher`, `exec_activate_alt_supplier.cypher`, `exec_expedite.cypher`, `exec_split_order.cypher`, `exec_place_hold.cypher`, `exec_notify_owner.cypher` | Must be approved unless auto-approvable. Stores the before-state in `undo_json` |
| `undo_action(action_id)` | | Creates a reverse Action and restores the before-state |
| `draft_notification(action_id)` | | `ChatMessage` to the owner linked to the Action |
| `get_playbook(disruption_type)` | memory | Highest success_rate, tie-break by uses |
| `recall_similar_episodes(incident_id)` | memory | See 3.5 |
| `record_episode(incident_id)` | memory | At incident close; updates Playbook uses/successes |
| `upsert_fact(subject_id, predicate, object, source)` / `facts_about(subject_id, include_history)` | memory | Contradiction → old fact gets `invalid_at` + `SUPERSEDES` |

Action effects must make `revenue_at_risk` drop. Define "impacted" precisely and consistently:

* Port closure: an open order is impacted if its current `SHIPS_VIA` lane has ORIGIN or DEST at an affected port.
  `REROUTE_ORDERS` re-points `SHIPS_VIA` to a lane that avoids the port (creating the lane if needed, with
  `transit_days` from `alt_route`) → those orders leave the impact set.
* Supplier failure: an open order is impacted if any of its products has a part whose **active** SUPPLIES edges
  all come from affected suppliers (directly or upstream via SUPPLIES_TO*0..2). `ACTIVATE_ALT_SUPPLIER` turns a
  `QUALIFIED_FOR` into `SUPPLIES {share}` → the part is no longer fully dependent on affected suppliers → orders
  leave the impact set. (A part with at least one unaffected active supplier is "degraded", not "impacted";
  report it separately.)
* Carrier strike: lanes with that `carrier` are affected; reroute moves orders to a lane with another carrier.
* `PLACE_HOLD`, `EXPEDITE`, `NOTIFY_OWNER` don't change the impact set (they change cost/status/messages).

Auto-approval policy (`ripple/tools/actions.py`): `NOTIFY_OWNER` and `PLACE_HOLD` auto-execute.
`REROUTE_ORDERS` auto-executes if the added transit days ≤ 3 and the order count ≤ 50. Everything else stays
`proposed` until a human approves (Action Queue). Put the thresholds in config.

### 4.1 MCP server (`ripple/mcp_server.py`)

* `FastMCP("ripple")`; every registry tool registered with its schema. Tool functions must not take
  `tenant_id`. The tenant comes from (in order): a `contextvars.ContextVar` set by the in-process caller, or the
  `RIPPLE_TENANT` env var for stdio mode (one server per tenant). Reject any call when no tenant is set.
* Also expose MCP resources: `ripple://ontology` (schema + counts) and `ripple://incident/{id}`.
* `python -m ripple.mcp_server --tenant dataco` runs stdio (for Claude Desktop, against a remote FalkorDB).
* Test with `async with fastmcp.Client(mcp) as c: await c.call_tool(...)` (in-memory transport). Results expose
  `.data` and `.structured_content` (verified on fastmcp 4.1.0). Use `tool.input_schema` (not `inputSchema`).

---

## 5. Agents (`ripple/agents/`)

### 5.1 Orchestration (LangGraph)

```python
from langgraph.graph import StateGraph, START, END
class IncidentState(TypedDict):
    tenant_id: str
    incident_id: str | None
    event: dict
    mode: Literal["scripted", "llm"]
# nodes: sentinel -> [analyst, comms_prefetch] (parallel fan-out) -> planner -> comms -> close
```

State holds only ids. All substantive results are written to the graph (Incident blackboard). Each agent, when
done, writes `(:Agent {name})-[:HANDED_OFF_TO {incident_id, ts, summary}]->(:Agent)` and emits an event to
`ripple/agents/events.py` (in-process asyncio pub/sub keyed by incident id) that the SSE endpoint streams.

Event shape (the UI depends on it, keep it stable):

```json
{"seq": 3, "ts": 1792017102401, "incident_id": "INC-…", "agent": "analyst",
 "kind": "tool_call|tool_result|handoff|message|action|done|error",
 "tool": "blast_radius", "args": {...}, "summary": "412 open orders, $1.23M at risk",
 "node_ids": [...], "edges": [[...]], "data": {...}}
```

### 5.2 Scripted mode (default; must hit every tool the demo needs)

| Agent | Steps |
|---|---|
| Sentinel | `match_event_to_entities` → `create_disruption` → `open_incident` → `recall_similar_episodes` → message "Similar to INC-… (score 0.82); playbook P-port-closure has 83% success" |
| Analyst | `blast_radius` → `revenue_at_risk` → `customer_exposure` → `late_risk_baseline` for the top impacted lane mode/market → `single_points_of_failure(top_k=5)` (flags chokepoints among affected suppliers) |
| Comms prefetch (parallel with Analyst) | `who_owns` for affected suppliers/ports' related suppliers; `contract_terms(supplier, 'delay penalty')` |
| Planner | `get_playbook` → for each playbook step: port closure → `alt_route` then `propose_action(REROUTE_ORDERS)`; supplier failure → for each impacted part `alt_suppliers` then `propose_action(ACTIVATE_ALT_SUPPLIER)`; always `propose_action(NOTIFY_OWNER)`; auto-execute per policy; `revenue_at_risk` after |
| Comms | `draft_notification` for each executed/proposed action with owner, contract clause and numbers; final incident summary message with sources |
| Close (called when all actions are resolved, or explicitly via API) | `record_episode` (outcome from revenue before/after), `upsert_fact` (e.g. supplier reliability dropped), `SAVE` |

### 5.3 LLM mode (`ripple/agents/llm.py`)

* Uses the official `anthropic` SDK. Read `reference/claude-api/tool-use.md` and `README.md` before writing it.
  Model from `RIPPLE_MODEL` (default `claude-opus-5-5`). Use a **manual tool-use loop** (we need per-call logging,
  event emission, and tenant scoping), `tool_choice={"type":"auto"}` (forced tool choice returns 400 on current
  models), `thinking={"type":"adaptive"}`, `output_config={"effort":"medium"}`, `max_tokens=16000`.
  Do not send `temperature` or `budget_tokens` (rejected). Return all `tool_result` blocks for one assistant turn in
  a single user message; on tool error return `is_error: true`.
* Each agent gets a system prompt with its role, the ontology summary, and the subset of tools it may use (§7 of
  idea.md). The orchestrator is the same LangGraph; each node runs either scripted logic or the LLM loop.
* **ID validator:** after the final answer, extract every `[A-Z]{2,5}-[\w-]+` token; any id not present in the
  union of `node_ids` from this run's tool results is rejected and the model is asked once to fix it; if it fails
  again, fall back to the scripted answer for that agent.
* `FakeAnthropic` test double that replays a scripted sequence of `tool_use` blocks, so the loop, logging,
  validator and event emission are tested without a key.
* If `ANTHROPIC_API_KEY` is unset, `mode="llm"` silently downgrades to scripted and the API reports
  `"mode": "scripted (no API key)"`.

### 5.4 Company brain `ask(question)` (`ripple/tools/brain.py`)

Router (scripted): keyword/regex intent → tool(s):

| Intent | Triggers | Tools |
|---|---|---|
| owner | "who owns", "owner", "relationship with", "backs them up" | entity resolution → `who_owns` (+ team members as backup) |
| why | "why did we", "reason", "decided" | `trace_decision` |
| contract | "contract", "penalty", "clause", "SLA", "owed" | `contract_terms` (+ penalty math if an incident is in context) |
| expertise | "who knows", "handled", "experience" | `who_knows` |
| change | "what changed", "since", "policy" | decisions + facts ordered by time, docs with newer `version` |
| fallback | anything else | `doc_search` |

Entity resolution: dictionary lookup of names/ids in the question (same dictionary as entity linking).
Answer contract: `{answer: str, sources: [{doc_id, title, uri, chunk_id?, snippet}], path: [node ids], edges, intent}`.
Answers are composed from templates in scripted mode, or by Claude (LLM mode) with the same tool results and the
ID validator. Every conversation turn is stored in `mem_<tenant>` (`ConvMessage` with `sources_json`).

---

## 6. API (`ripple/api/`, FastAPI)

`create_app(settings)` builds the app; the lifespan opens the DB (embedded or remote), applies the schema, and
builds tenants if the graphs are empty and `RIPPLE_AUTOBUILD=1` (default 1 for embedded). The tenant is a header
`X-Ripple-Tenant: dataco|nova` (default dataco); unknown tenant → 404.

| Method & path | Purpose |
|---|---|
| `GET /api/health` | `{ok, db_mode, graphs, agent_mode}` |
| `GET /api/tenants` | List tenants with node/edge counts |
| `GET /api/ontology` | Labels, rel types, properties, counts (`db.meta.stats()`), plus the static ontology description |
| `GET /api/map` | Ports, plants, suppliers with lat/lon, risk_score, status, active disruptions |
| `GET /api/scenarios` | Scenario list from `data/scenarios/*.yaml` |
| `POST /api/incidents` | Body `{scenario_id}` or `{event}` + `mode`. Starts the orchestrator as a background task; returns `{incident_id}` immediately |
| `GET /api/incidents` / `GET /api/incidents/{id}` | Incident + disruption + numbers + actions + handoffs |
| `GET /api/incidents/{id}/events` | **SSE** (sse-starlette `EventSourceResponse`): replays past events then streams live ones; ends after `done` |
| `GET /api/incidents/{id}/graph` | Highlight subgraph `{nodes:[{id,label,name}], links:[{source,target,type}]}` capped at 300 nodes |
| `POST /api/incidents/{id}/close` | Close → record episode |
| `GET /api/actions?status=proposed` | Action queue |
| `GET /api/actions/{id}` | Action + evidence (Q9) |
| `POST /api/actions/{id}/approve` · `/reject` · `/execute` · `/undo` | Lifecycle; returns revenue at risk before/after |
| `POST /api/brain/ask` | `{question, user_id, conversation_id?}` → answer contract |
| `POST /api/brain/ingest` | Delta ingest of a chat message/doc (demo: owner handover) |
| `GET /api/memory/episodes` · `/playbooks` · `/facts?subject_id=` · `/conversations?user_id=` | Memory inspector |
| `GET /api/algos/spof` · `/influence` · `/clusters` | Algorithm panels |

In production the app also serves `ui/dist` at `/` (StaticFiles with SPA fallback) so a single container deploys
everything.

---

## 7. UI (`ui/`, Vite + React 19 + TS + Tailwind 4)

The cloud session can only verify the UI by `npm run build` (which includes `tsc`). Keep it simple, typed, and
driven by the API contract above. Put all API types and calls in `ui/src/api.ts`.

| Route | Content |
|---|---|
| `/` Control Tower | Leaflet map (OSM tiles) with ports, plants, suppliers (color by risk), active disruptions; scenario cards with **Trigger** buttons; incident list; tenant switcher in the header (stored in localStorage, sent as `X-Ripple-Tenant`) |
| `/incidents/:id` | Left: live agent timeline from SSE (agent avatar, tool chip, summary, handoff arrows). Center: `react-force-graph-2d` blast-radius graph; nodes colored by label, highlighted path edges animated (`linkDirectionalParticles`), click node → side panel with properties. Right: revenue at risk before → after, orders, customers, recalled episode + playbook card |
| `/actions` | Action queue table; evidence drawer (Q9 evidence list with links that highlight nodes); Approve / Reject / Execute / Undo |
| `/brain` | Chat; answers with source chips (click → show chunk text + uri) and "path" chips; a "Post chat message" box that calls `/api/brain/ingest` (owner handover demo) |
| `/memory` | Episodes table, playbooks with success rates, facts with validity windows (history toggle), conversations |
| `/ontology` | Schema diagram (force graph of labels as nodes, rel types as links, sized by counts) + counts table |

Import Leaflet CSS from `leaflet/dist/leaflet.css`. Keep the bundle building with `tsc -b && vite build` and
zero type errors. Dark, dense "control tower" look; no external fonts required.

---

## 8. Testing strategy (no server, no keys)

`tests/conftest.py`:

* Session fixture `built_db`: temp dir, embedded FalkorDB, builds **both tenants** with a **sample** of DataCo
  (`sample_orders=3000`, chosen deterministically: all orders for the 40 products made at Shanghai/Shenzhen plants
  first, then a seeded random fill) so tests run in seconds. Expose `scope_dataco`, `scope_nova`.
* `full_db` fixture (marker `@pytest.mark.slow`) builds the full dataset; run once at the end (`pytest -m slow`)
  and record the timing.
* API tests use `fastapi.testclient.TestClient` on `create_app` pointed at the built temp DB; SSE tested by
  reading the stream until `done`.

Required test files (each must exist and pass):

| File | Asserts |
|---|---|
| `test_schema.py` | Schema applies twice without error; indexes exist (`CALL db.indexes()`) |
| `test_ingest_dataco.py` | Counts match pandas for the sample; no PII property keys anywhere (`db.propertyKeys()` contains none of email/fname/lname/password/street/zipcode); every Order has exactly one SHIPS_VIA |
| `test_synth.py` | Generator is deterministic (two runs → identical file hashes); shares per part sum to 1; 20% ±2% single-sourced; hero entities exist; nova ids never collide with dataco ids |
| `test_queries.py` | Every `graph/queries/*.cypher` file parses and runs with its documented example params |
| `test_impact.py` | For each of the 4 scenarios: `blast_radius` order ids and revenue **exactly equal** `eval/ground_truth.py` |
| `test_algos.py` | 3 planted chokepoints in top 5 betweenness; PageRank returns scores; clusters cover all suppliers; `alt_route` avoids the closed port and is no shorter than the original |
| `test_late_risk.py` | `late_risk_baseline` equals the pandas mean for 3 (mode, market) pairs |
| `test_actions.py` | propose→approve→execute lowers `revenue_at_risk`; undo restores it; executing twice is a no-op; duplicate propose returns the same action id; evidence ids are BASED_ON-linked |
| `test_agents_scripted.py` | Full orchestrator run per scenario: handoffs in order sentinel→analyst/comms→planner→comms; incident has numbers; at least one action executed; events stream ends with `done`; wall time < 60 s |
| `test_agents_llm.py` | FakeAnthropic drives the loop; tool calls are logged; a fabricated id in the final answer is caught by the validator |
| `test_memory.py` | Run scenario A, close, record episode; **close the DB object, reopen from the same file** (simulated restart); run scenario B (similar) → Sentinel's recall cites A's episode and Planner uses the same playbook; playbook success counts updated; fact contradiction sets `invalid_at` |
| `test_tenancy.py` | `TenantScope('dataco')` cannot open `tenant_nova`; same question on both tenants returns disjoint ids; MCP call without tenant fails |
| `test_concurrency.py` | 20 threads × 2 tenants running read tools + duplicate proposes concurrently → no cross-tenant ids, no duplicate Actions, no exceptions |
| `test_brain.py` | The 5 demo questions in idea.md §11 return the expected source doc ids; `ingest_delta` owner handover changes `who_owns` answer; conversation stored |
| `test_mcp.py` | In-memory FastMCP client lists all registry tools; calling `blast_radius` returns node_ids; tool schemas have no `tenant_id` |
| `test_api.py` | Every endpoint in §6 returns 2xx on the happy path; SSE yields events then `done`; approve endpoint returns before/after revenue |

Eval scripts (run at the end, outputs pasted into README by `scripts/report_numbers.py`):
`eval/run_scenarios.py` (4/4 exact), `eval/run_brain_eval.py` (≥18/20), `eval/load_test.py` (20 sessions, 0 leaks,
0 duplicates; report p50/p95 latency).

UI: `cd ui && npm run build` must pass.

---

## 9. Milestones (do them in order; commit after each)

Each milestone lists its **done-when**. The session should go M0 → M12 without stopping.

### M0. Environment and skeleton
* Run `bash scripts/setup_env.sh` (skip if `.venv` exists and `scripts/verify_falkordb.py` passes).
* Create the `ripple/` package layout from §2, `ripple/config.py`, `ripple/db.py` (`get_db`, `TenantScope`,
  `save()`), `ripple/graph/queries.py`, `tests/conftest.py` with a trivial test.
* Done when: `.venv/bin/pytest -q` passes; `.venv/bin/python -c "import ripple"` works.

### M1. Ontology, schema, DataCo loader
* `graph/schema.cypher`, `ripple/graph/schema.py` (idempotent; catches "already indexed").
* `ripple/ontology.py`: single source of truth for labels/rels/properties → generates `graph/ontology.md`.
* `ripple/ingest/dataco.py`: read gz with latin-1, drop PII columns at read time (`usecols`), strip region names,
  build orders/lines/products/customers/markets/regions, batched `UNWIND` (5K rows), `--sample N`.
* Done when: `test_schema.py`, `test_ingest_dataco.py` pass.

### M2. Synthetic generator and loader
* `ripple/ingest/synth.py` per §3.3 (both tenants), committed outputs in `data/synthetic/`.
* `ripple/ingest/load_synth.py`, materialize `CONNECTS`, `RiskBearing` label on Supplier/Port/Lane.
* `ripple/ingest/build.py` CLI: `python -m ripple.ingest.build --tenant dataco [--sample 3000] [--db var/ripple.db]`.
* Done when: `test_synth.py` passes and a full build of dataco completes (record time and counts).

### M3. Documents and company-brain ingest
* Generate docs/chats (templated markdown/JSON with front matter) in the generator.
* `ripple/embed.py` HashEmbedder: lowercase tokens + bigrams → feature hashing (blake2b) into 384 dims with signed
  buckets, L2-normalize. Deterministic across runs and processes.
* `ripple/ingest/docs.py` per §3.4; vector index on `Chunk.embedding` and `ChatMessage.embedding`.
* Done when: chunk/mention/decision counts are non-zero and `doc_search("battery dual source")` returns the
  typhoon postmortem in top 3 (add this as a test in `test_brain.py`).

### M4. Scenarios and ground truth
* `data/scenarios/`: `port_closure_shanghai.yaml` (CNSHA, 10 days), `port_congestion_ningbo.yaml` (CNNGB — the
  "similar" scenario for the recall demo), `tier2_fire.yaml` (one planted chokepoint tier-2 supplier),
  `carrier_strike.yaml` (one carrier). Also `quality_hold.yaml` if time permits.
* `eval/ground_truth.py`: pandas-only, from `data/raw` + `data/synthetic` files.
* Done when: ground truth prints non-trivial numbers for each scenario on the test sample and the full data
  (each scenario hits ≥ 50 open orders on the full data; tune the generator if not).

### M5. Read tools, algorithms, query files
* All read/algo tools from §4 with their `.cypher` files, `ToolResult`, `logged_tool`.
* Done when: `test_queries.py`, `test_impact.py`, `test_algos.py`, `test_late_risk.py` pass.

### M6. Actions (write-back)
* propose/approve/reject/execute/undo + effects + auto-approval policy.
* Done when: `test_actions.py` passes.

### M7. Memory
* Memory tools (§3.5), seeded playbooks/episodes, facts with supersession, conversation log, `SAVE` on close.
* Done when: memory unit tests pass (the restart test lands in M8 once agents exist).

### M8. Agents and orchestration
* Scripted agents, LangGraph orchestrator, event bus, HANDED_OFF_TO, close step.
* LLM loop + FakeAnthropic + ID validator.
* Done when: `test_agents_scripted.py`, `test_agents_llm.py`, `test_memory.py` (restart recall) pass.

### M9. Company brain and delta ingest
* `ask()` router, answer contract, `who_knows`, `trace_decision`, `ingest_delta` (owner handover closes the old
  OWNS_RELATIONSHIP window and opens a new one, adds a ChatMessage + MENTIONS, adds a Fact).
* `eval/brain_questions.yaml` (20 questions covering the 5 intents, with expected doc ids) + `run_brain_eval.py`.
* Done when: `test_brain.py` passes and brain eval ≥ 18/20.

### M10. MCP server, tenancy, concurrency
* `ripple/mcp_server.py`, tenant ContextVar, stdio entry point.
* Done when: `test_mcp.py`, `test_tenancy.py`, `test_concurrency.py` pass; `eval/load_test.py` passes.

### M11. API and UI
* FastAPI per §6 with SSE; serve `ui/dist`.
* UI per §7.
* Done when: `test_api.py` passes and `cd ui && npm run build` passes.

### M12. Packaging, docs, numbers
* `Dockerfile` (python:3.12-slim, `pip install -r requirements.lock`, build UI in a node stage, copy `ui/dist`,
  `RIPPLE_DB_MODE` from env, `uvicorn ripple.api.app:app`), `docker-compose.yml` (falkordb/falkordb:latest +
  api in remote mode), `render.yaml`. Mark them "not run in the build session" in KNOWN_ISSUES.
* `scripts/report_numbers.py`: full build time, node/edge counts per label/type and per tenant, query latencies
  (p50 of 20 runs for Q1–Q10), scenario eval, brain eval, load test. Writes `docs/numbers.md`.
* `scripts/demo.py`: CLI run of the 3 demo acts (incident + approve; restart + recall + tenant switch; brain
  questions + handover) printing the timeline, for a terminal fallback demo.
* `README.md`: pitch; tracks entered (01, 02, 03); architecture diagram (mermaid); **ontology** (from
  `graph/ontology.md`); **every query** (generated from `graph/queries/*.cypher` with its purpose line);
  algorithms used; "Why a graph / no FalkorDB, no product" section; setup (embedded quickstart, Docker, FalkorDB
  Cloud); data sources with citations and licenses (DataCo CC BY 4.0, synthetic data labeled); PII handling;
  numbers from `docs/numbers.md`; eval results; demo script (idea.md §17).
* `AI_DISCLOSURE.md`: Claude Code wrote most of the code from a human-written spec (idea.md); list what the human
  must verify and own (ontology, queries, scenario ground truth, demo) — leave clearly marked TODOs for the human to
  fill in what they personally reviewed.
* `docs/blog.md` draft per idea.md §19 using real numbers.
* `LICENSE` (MIT).
* Done when: full `pytest` (including `-m slow`) passes, `npm run build` passes, README has no placeholder numbers.

---

## 10. Final report the session must leave

Write `docs/BUILD_REPORT.md` and end the session with a summary that states:
* Which milestones are done, test counts (passed/failed/skipped), and the exact commands to reproduce.
* What was **not** verified in the cloud session (Docker, remote FalkorDB, FalkorDB Cloud, real Claude calls,
  Graphiti, the UI in a browser, deploy) and the exact steps the human should run locally to verify each.
* Every deviation from this plan and why.

---

## 11. After the cloud session (human, local)

1. `bash scripts/setup_env.sh` on the laptop (macOS uses the network for wheels; that's fine).
2. `docker run -p 6379:6379 -p 3000:3000 falkordb/falkordb:latest`, set `RIPPLE_DB_MODE=remote`, build tenants,
   open the FalkorDB Browser at :3000 for screenshots.
3. Set `ANTHROPIC_API_KEY`, run an incident with `mode=llm`, check the tool trace.
4. `uvicorn ripple.api.app:app --reload` + `cd ui && npm run dev`; click through the demo.
5. Deploy (FalkorDB Cloud + Render/Railway single container, or embedded mode in one container with a volume).
6. Record the video, publish the blog, submit with tracks 01/02/03.
