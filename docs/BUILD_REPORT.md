# Build report (autonomous Claude Code session, plan.md M0-M12)

## Milestones

| Milestone | Status | Done-when evidence |
|---|---|---|
| M0 Environment and skeleton | done | `ripple` imports; smoke test green (after fixing the sampled-betweenness check) |
| M1 Ontology, schema, DataCo loader | done | `test_schema.py`, `test_ingest_dataco.py` |
| M2 Synthetic generator and loader | done | `test_synth.py`; full dataco build ~30 s (see `docs/numbers.md`) |
| M3 Documents and brain ingest | done | `doc_search("battery dual source")` returns the typhoon postmortem in the top 3 (`test_brain.py`) |
| M4 Scenarios and ground truth | done | `eval/ground_truth.py`: every scenario ≥ 50 open orders on full data (smallest: tier-2 fire, 1,333) |
| M5 Read tools, algorithms, query files | done | `test_queries.py`, `test_impact.py` (exact), `test_algos.py`, `test_late_risk.py` |
| M6 Actions | done | `test_actions.py` |
| M7 Memory | done | `test_memory.py` (unit tests) |
| M8 Agents and orchestration | done | `test_agents_scripted.py`, `test_agents_llm.py`, `test_memory.py::test_restart_recall_reuses_playbook` |
| M9 Company brain and delta ingest | done | `test_brain.py`; brain eval 20/20 |
| M10 MCP, tenancy, concurrency | done | `test_mcp.py`, `test_tenancy.py`, `test_concurrency.py`; `eval/load_test.py` 0 leaks / 0 duplicates |
| M11 API and UI | done | `test_api.py`; `cd ui && npm run build` passes; all pages rendered against the live API in headless Chromium |
| M12 Packaging, docs, numbers | done | Dockerfile/compose/render written; `scripts/report_numbers.py` → `docs/numbers.md`; README generated; slow tests pass |

## Test results (final run)

| Suite | Command | Result |
|---|---|---|
| Fast (embedded, DataCo sample of 3,000 orders + Nova) | `.venv/bin/pytest -q` | 213 passed, 3 deselected (slow), ~1.5 min |
| Slow (full DataCo) | `.venv/bin/pytest -m slow` | 3 passed (full build 30.6 s; 4/4 scenarios exact; chokepoints top 5; brain ≥ 18/20) |
| Remote (FalkorDB server in Docker, `falkordb/falkordb:v4.18.3`) | `RIPPLE_DB_MODE=remote .venv/bin/pytest -q` | 213 passed, 3 deselected |
| UI | `cd ui && npm run build` | passes (`tsc -b` with zero errors + `vite build`) |
| Smoke test | `.venv/bin/python scripts/verify_falkordb.py` | 17/17 checks |
| Scenario eval (full) | `.venv/bin/python eval/run_scenarios.py --full` | 4/4 exact |
| Brain eval | `.venv/bin/python eval/run_brain_eval.py` | 20/20 |
| Load test | `.venv/bin/python eval/load_test.py` | 20 sessions, 0 leaks, 0 duplicate actions |
| Numbers | `.venv/bin/python scripts/report_numbers.py` | writes `docs/numbers.md`; README via `scripts/build_docs.py` |

## Reproduce

```bash
bash scripts/setup_env.sh
.venv/bin/pytest -q && .venv/bin/pytest -m slow
cd ui && npm run build && cd ..
.venv/bin/python scripts/report_numbers.py && .venv/bin/python scripts/build_docs.py
.venv/bin/python scripts/demo.py            # terminal walkthrough of the 3 demo acts
.venv/bin/uvicorn ripple.api.app:app        # http://localhost:8000
```

## Not verified in this session, and how to verify locally

| Item | Steps |
|---|---|
| Docker image / compose / Render | `docker compose up --build`; open http://localhost:8000 and the FalkorDB Browser at http://localhost:3000 |
| FalkorDB Cloud | `RIPPLE_DB_MODE=remote FALKORDB_HOST=... FALKORDB_PORT=... FALKORDB_USERNAME=... FALKORDB_PASSWORD=... python -m ripple.ingest.build`, then start the API |
| Real Claude calls | `export ANTHROPIC_API_KEY=...`; in the UI choose "Claude agents" before Trigger; check the tool trace in the timeline (`/api/health` shows `agent_mode: llm`) |
| Graphiti | Not built (optional in the plan) |
| UI interactions in a real browser | `uvicorn ripple.api.app:app` + click through the demo (Trigger, Approve, Close, Ask, Post handover, tenant switch) |
| MCP with Claude Desktop | Add the README's config; ask Claude to call `blast_radius` |
| Deployment | `render.yaml` or any container host with a persistent volume for `/app/var` |

Remote mode was verified (the whole test suite against a FalkorDB server in Docker), which the plan listed as an
optional bonus.

## Deviations from the plan

See [KNOWN_ISSUES.md](KNOWN_ISSUES.md): FalkorDB findings (sampled betweenness, `CALL {UNION}` binding,
full-text index syntax on the newer server, `latest` image panic, `GRAPH.COPY`, approximate vector index, socket
timeout, redislite shutdown), data-volume differences (26 ports, 746 lanes, 2,128 supply edges, department
specialties for tier-1 suppliers), API/tool additions, and the optional items not built (quality-hold scenario,
Graphiti).
