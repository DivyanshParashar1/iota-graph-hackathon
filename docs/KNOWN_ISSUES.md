# Known issues, deviations and things not verified

Recorded during the autonomous v2 build session (plan.md rule 4: nothing is declared done on the strength of a
code path that was never executed). Each item says what happened and what was done about it. v1's list is in
the git history of this file at tag/commit `v1-dataco`.

## FalkorDB findings turned on in v2

| Finding | Effect | Resolution |
|---|---|---|
| **`MERGE` on an unlabelled pattern scans the graph.** The first instance loader matched edge endpoints as `MATCH (a {id: r.from})`, with no label, so no id index could be used | Loading 6,000 nodes + 5,500 edges took **16.3 s** | `instance_merge_edges` is a template in `from_label`/`to_label` too, and `load_instances` groups edges by `(relationship, from label, to label)`. Same load: **0.33 s** (~50×). Measured in `docs/numbers.md` |
| Map-valued properties are rejected ("Property values can only be of primitive types or arrays of primitive types") | A generated property whose value is an object would fail the load | `graph/apply.py:_flat` flattens one level (`geo` → `geo_lat`, `geo_lon`) and JSON-encodes anything deeper; a list of primitives is stored as a list |
| Re-running `CREATE INDEX` raises | Approving an ontology twice, or restarting the API, would fail | Both the platform schema and `apply_spec` treat an "already exists" error as success (`graph/schema.exists_error`) |
| A per-tenant ontology cannot be parameterised: Cypher has no `MERGE (n:$label)` | Labels have to be interpolated into query text | Labels pass `validate_spec`, then exactly one guarded interpolation point (`graph/queries.ident`, `^[A-Za-z][A-Za-z0-9_]{0,63}$`). Query text stays in `graph/queries/*.cypher` as `kind: template`; `tests/test_validate.py` includes injection attempts |
| `DETACH DELETE` on "everything that is not platform state" is how a re-approved ontology is reloaded | A wipe could take the onboarding state with it | `instance_wipe` filters on `NOT any(l IN labels(n) WHERE l STARTS WITH '_')`, which is why every platform label is `_`-prefixed and why a generated label starting with `_` is rejected |
| redislite only shuts its server down when it holds the only client connection | Embedded servers outlived test runs | `DB.close()` disconnects the pool and forces `SHUTDOWN` (kept from v1) |

## Agent and provider findings

| Finding | Effect | Resolution |
|---|---|---|
| **A recursive pydantic model cannot be a structured-output schema.** `FormField.fields` was `list[FormField]`, and inlining `$ref`s produced a schema whose innermost `fields` was no longer an array | Every live data-agent call failed: `claude exited 1: .../fields/items must be array` — and *no* deterministic test caught it, because the schema was only validated by the provider | A group's columns are now a separate non-recursive `FormColumn` (a group inside a group is a schema, not a form). `json_schema` raises `RecursiveModel` instead of truncating, and `test_every_agent_turn_schema_is_flat_and_finite` builds every schema the agents send |
| The interviewer's "three to five questions" came back as five numbered asks with sub-clauses, i.e. 11 question marks | The first live assertion (`reply.count("?") <= 6`) failed on good output | The test counts the numbered/bulleted asks the user actually sees, plus a word cap. The prompt rule is unchanged |
| Claude Code's structured output is returned under `structured_output`, with the JSON also in `result` | A provider that returns only `result` would look like a failure | `run_claude` prefers `structured_output` and falls back to parsing `result`, and raises `LLMError` when neither is usable |
| `claude -p` inherits the ambient `ANTHROPIC_API_KEY` | A key in the environment would be billed instead of the CLI login | The subprocess environment drops `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN`, and runs in a temp directory so no project `CLAUDE.md` or settings leak into the prompt |
| An LLM can propose an expert role with no ontology footprint, or a spec that fails validation | The user would be asked to approve something unusable | Both go back to the agent with the list of errors, up to twice (`REPAIRS`), and only then surface as a system message |

## Deviations from plan.md

| Plan | Built | Why |
|---|---|---|
| §5: add `openpyxl` / `pypdf` / `python-docx`, or route binaries through the bridge | Neither: `.docx` and `.pdf` text is extracted with the standard library (`zipfile` + regex for docx; a content-stream reader for pdf), `.xlsx` goes through pandas and says so clearly if `openpyxl` is missing | The vendored dependency set is a hard constraint for the offline build (`CLAUDE.md`), and the agents only ever see a profile or a summary, so a best-effort text extract is enough. A scanned PDF is refused with a message that says to upload the text instead |
| §3: `_Session.pending` as a field | `pending_json` on `_Session` | FalkorDB rejects map-valued properties; the same reason the artifact bodies are JSON strings |
| §4.1: the brief is a new version per turn | One open version is patched in place; a new version is cut when the current one is approved or has been flagged stale | A version per turn would make the history unreadable. Jumping back marks the brief's downstream artifacts stale, and the next edit cuts v2 — which is what the versioning is for |
| §4.3: the ontology agent loads the instance data | It does, in a second structured call at approval time (`ontologist.approve`) | One call cannot both design a model and read a data pack into it reliably; splitting them also means a re-approval reloads without redesigning |
| §9 M5: "a minimal read-only tool set" | 6 tools: `describe_ontology`, `find_nodes`, `get_node`, `neighbours`, `aggregate`, `provenance` | Enough for a generated role to answer a real question from the graph. The richer set is §10's |
| §8: "API routes driven with agent calls patched out at the provider boundary" | `tests/conftest.StubClient` | As planned. It implements the provider protocol and replays payloads the test wrote; it has no prompt and no logic |
| v1's `/api/tenants` switcher | Kept, and `POST /api/tenant/select/{id}` | One user = one tenant (§9.1.3), but a demo needs to walk back into a tenant it built earlier |

## Not verified in this session

| Item | Status | How to verify locally |
|---|---|---|
| `Dockerfile` / `docker compose up --build` / `render.yaml` | Updated for v2 (no dataset to copy, no autobuild), **not built or run** — the image build needs PyPI and npm inside Docker, which the build sandbox does not have | `docker compose up --build`, then http://localhost:8000. Claude Code runs on the host, so start the bridge first: `.venv/bin/python -m ripple.claude_code_bridge` |
| The Claude Code **bridge** path (`CLAUDE_CODE_BRIDGE_URL`) | Unit-tested against a fake transport; not run across a real container boundary | Start the bridge, then `CLAUDE_CODE_BRIDGE_URL=http://127.0.0.1:8765 .venv/bin/pytest -m llm -k provider_answers` |
| Remote mode (`RIPPLE_DB_MODE=remote`) | The suite is written to run against a server (the `db` fixture flushes a logical database), but Docker is not available in the build sandbox, so v2's suite has only run embedded | `docker run -d -p 6379:6379 falkordb/falkordb:v4.18.3` then `RIPPLE_DB_MODE=remote .venv/bin/pytest -q`. `:latest` panicked in v1 — keep the pin |
| OpenRouter and Anthropic providers | Request translation and response parsing are unit-tested; no live call was made (no key in the sandbox) | Set the key, `RIPPLE_LLM_PROVIDER=openrouter .venv/bin/pytest -m llm -k provider_answers` |
| The UI in an interactive browser | **Rendered**, not clicked: all four pages were loaded in headless Chromium against the live API with a real tenant, and `docs/img/*` are those screenshots (v1's are gone). No interaction was automated, so forms, approve, edit-a-prompt and ask-an-expert have been exercised through the API and the test suite but not through the browser | `.venv/bin/uvicorn ripple.api.app:app` + http://localhost:8000, or replay a recorded run first with `scripts/seed_from_run.py` |
| `.xlsx` upload | Code path written; `openpyxl` is not in the vendored set, so it raises the "export as CSV" message | `pip install openpyxl` and upload a sheet |
| The full live onboarding (`-m "llm and slow"`) | **Verified.** One run end to end: 4 interview turns, 2 form rounds, a 12-type / 25-relationship ontology, 22 instance nodes with 31 provenance links, 6 expert roles, 3 of them asked a playbook question. 25 provider calls, 10m33s. Recorded in `artifacts/llm_runs/20261015-204539` and summarised in `docs/numbers.md` | `.venv/bin/pytest -m llm -k full_onboarding -s` (expect ~10 minutes and real spend) |

## What the verified live run exposed

Not bugs - product findings from watching the whole thing run on one company (a mid-sized shoe
manufacturer, played by a second model).

| Finding | Why it matters |
|---|---|
| **The data pack collects structure, not transactions.** The data agent asked for suppliers, components, sites, lanes, customers and terms - and never for a single order or shipment, because the brief never said "and here are our open orders". So the graph has `Order` and `Shipment` *types* with zero instances | Three of the six generated roles were asked a playbook question and correctly answered *"the graph has no orders, and I am not going to make up numbers"*, citing the nodes that do exist. That is exactly the honesty the prompts ask for, and it is also the demo's ceiling: an expert cannot show operational analysis over data nobody collected. Either the data agent should ask for a sample of live transactions, or the expert generator should scope playbooks to the types that have instances. **Decide before M8** |
| The ontology agent declared `Order`, `Shipment` and `RiskEvent` from the brief's *pains* rather than from the data pack | Right call for a model (the pains are the requirements), and it means `coverage.unmapped_answers` is not the only honesty signal: a type with no instances is one too. The UI shows instance counts per type on the ontology page, which is where that shows up |
| Six roles, 361-460 words of system prompt each, all grounded | No role was rejected by `validate_roles` on the first attempt in this run, so the repair loop was not exercised live (it is covered deterministically) |

## Carried over from v1 and still true

* `falkordb/falkordb:latest` (the Rust server) panicked during a v1 build; `docker-compose.yml` pins `v4.18.3`.
* `EXISTS { MATCH ... }` is not supported; use a pattern predicate or `OPTIONAL MATCH` + `IS NULL`.
* `MATCH p = shortestPath(...)` only works inside `WITH`/`RETURN`.
* One process must own an embedded `.db` file: the API process owns it.
