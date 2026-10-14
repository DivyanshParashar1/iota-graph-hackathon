# Ripple (FalkorDB hackathon project)

Spec: `idea.md`. Build plan and milestones: `plan.md` (wins over idea.md). FalkorDB syntax truth:
`reference/FALKORDB_VERIFIED.md` (wins over both).

* Setup: `bash scripts/setup_env.sh` (offline from `vendor/`). Use `.venv/bin/python` and `.venv/bin/pytest`.
* Tests: `.venv/bin/pytest -q` (fast, sampled data) and `.venv/bin/pytest -m slow` (full dataset). UI: `cd ui && npm run build`.
* DB: embedded FalkorDB (`falkordblite`) by default (`RIPPLE_DB_MODE=embedded`); one process per `.db` file.
* Agents default to scripted mode; LLM mode needs `ANTHROPIC_API_KEY` (model `claude-opus-5-5`, Anthropic SDK docs in `reference/claude-api/`).
* Every product Cypher query lives in `graph/queries/*.cypher`; don't inline queries in Python.
* Don't add dependencies; everything is pinned in `requirements.lock` / `ui/package-lock.json` and vendored.
* Commit after each milestone with tests green.
