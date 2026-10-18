# Ripple (FalkorDB hackathon project)

v2 interviews a company and builds its supply chain knowledge graph. Build plan and milestones: `plan.md`
(wins over `idea.md`, which is v1's pitch). FalkorDB syntax truth: `reference/FALKORDB_VERIFIED.md` (wins over
both). v1 (a DataCo control tower) is at commit `04d4bd4` / local tag `v1-dataco`; its plan is
`docs/plan_v1_dataco.md`.

* Setup: `bash scripts/setup_env.sh` (offline from `vendor/`). Use `.venv/bin/python` and `.venv/bin/pytest`.
* Tests: `.venv/bin/pytest -q` (deterministic, no network) and `.venv/bin/pytest -q -m llm` (real LLM calls,
  costs money). `-m "llm and slow"` is the full end-to-end onboarding. `-m jev` calls the real Jev decision
  model. UI: `cd ui && npm run build`.
* **Only Jev decides** (M8, `docs/m8_decision_pipeline.md`). Jev is TypeSafe's decision model, not an LLM: it
  lives in `ripple/decide/`, never in `ripple/llm/`. The incident agents (`ripple/incident/agents/`) generate
  evidence, drafts and options; any choice - whom to ask, when to stop, which option, how urgent - is a Jev
  question, and autonomy is policy thresholds on its probabilities. Response shape truth:
  `reference/JEV_VERIFIED.md`. Tests reach Jev only through `tests/conftest.JevTransport` (the real client
  over a mock HTTP transport).
  **One owner-approved exception:** the workspace chat (`ripple/workspace/orchestrator.py`) is an LLM
  orchestrator that picks which expert agents to consult and when to stop. It only answers questions; it never
  approves or acts. Do not extend that exception to anything that decides or acts.
* **No fakes.** There is no scripted agent mode and no fake LLM client. `tests/conftest.StubClient` is a
  transport stub at the provider boundary for route tests - never add logic or prompts to it.
* Every agent step is a real LLM call through `ripple/llm/`. Default provider: the local `claude` CLI login
  (no API key). Anthropic SDK docs: `reference/claude-api/`.
* DB: embedded FalkorDB (`falkordblite`) by default (`RIPPLE_DB_MODE=embedded`); one process per `.db` file.
* Every product Cypher query lives in `graph/queries/*.cypher`; don't inline queries in Python. A query against
  a *generated* type is `kind: template` with `{placeholders}` filled by `Q(name, label=...)`, which validates
  each one through `ripple.graph.queries.ident`. That function is the only place a model-authored string may
  reach Cypher.
* Platform labels are `_`-prefixed (`_Tenant`, `_Session`, `_Brief`, ...) and `validate_spec` rejects any
  generated label starting with `_`. `instance_wipe` depends on that split.
* Don't add dependencies; everything is pinned in `requirements.lock` / `ui/package-lock.json` and vendored.
  If you change `ui/package.json`, regenerate the lockfile or `npm ci` breaks.
* The agents' prompts in `ripple/onboarding/agents/prompts/*.md` are product behaviour: change them
  deliberately, and re-run `-m llm -k prompt` afterwards.
* Commit after each milestone with tests green.
* Remote mode tests: `docker run -d -p 6379:6379 falkordb/falkordb:v4.18.3` then
  `RIPPLE_DB_MODE=remote .venv/bin/pytest -q` (`:latest` panics, see `docs/KNOWN_ISSUES.md`).
* README is generated: edit `docs/README.template.md`, then
  `.venv/bin/python scripts/report_numbers.py && .venv/bin/python scripts/build_docs.py`.
* `tenants/` and `artifacts/` are runtime output and git-ignored.
