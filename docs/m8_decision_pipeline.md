# M8: the incident pipeline and Jev

Status: **built, not yet executed.** The owner asked for the whole architecture to be written and to run it
themselves, so none of the tests, live suites or the UI build has been run (§11 lists exactly what to run). This
document is the spec; it wins over `plan.md` §10.

## 1. The one rule

**Only Jev decides.** Every other agent generates: it collects evidence, writes reports, drafts messages, and
proposes options. None of them picks. Each step that would otherwise be a decision inside an LLM agent is a Jev
question instead (§6). The LLM agents' job is to make the `state` Jev reads complete, sourced and short.

## 2. Flow

```
 POST /api/events/{tenant}   (any JSON with a free-text `summary`)            routes_incidents.py
        │  receive() -> _Incident(status=received)                             pipeline.receive
        ▼
   JEV: relevance  ── one noul per approved expert role -> who is consulted     pipeline.choose_experts
        ▼
   ORCHESTRATOR (LLM) ── round r: writes questions for the consulted experts    agents/orchestrator.plan_round
        │  experts answer in parallel from the tenant graph (M5 runtime)        experts/runtime.ask
        │  JEV: sufficiency ── one noul: is the evidence enough?                pipeline.consult
        │  loop until Jev says yes, the orchestrator has nothing left to ask,
        │  or RIPPLE_INCIDENT_MAX_ROUNDS
        ▼
   ORCHESTRATOR (LLM) ── evidence report: numbered, sourced claims E1..En       agents/orchestrator.write_report
        ▼
   ANALYST (LLM)  ‖  COMMS (LLM)      in parallel, both from the full report    pipeline.analyse_and_draft
   metrics with      one draft per recipient
   evidence basis
        ▼
   PLANNER (LLM) ── decision groups (exclusive | independent), options,          agents/planner.plan
        │           alternatives. No ranking, no recommendation.
        ▼
   DecisionPacket (assembled in code)  ->  Jev request (compiled in code)        pipeline.assemble, decide/compile
        ▼
   JEV: decision ── P(option) per exclusive group, P(yes) per independent        pipeline.decide
        │           action, a priority distribution for the event
        ▼
   POLICY (fixed thresholds, no model)                                          decide/policy
        ├─ critical & P(critical) >= 0.5 -> auto-approve Jev's choices  -> status auto_approved
        └─ otherwise                     -> every option pending          -> status awaiting_approval
        ▼
   People approve / reject (an approval in an exclusive group deselects its siblings; rejecting an
   auto-approved option undoes it). Each approved option shows its live impact on the graph.
```

Every agent reply passes a deterministic validator (`ripple/incident/validate.py`: experts that exist, node ids
that came back from tools, evidence ids that are in the report, an exclusive group that has exactly one wait
option). A rejected reply goes back to the model with the problems listed, and the agent gets two repair rounds.
A run that still fails is recorded on the incident with its error. It is never lost.

## 3. Jev (researched 2026-10-17; `reference/JEV_VERIFIED.md` is the truth)

* **What it is.** TypeSafe AI's "System One" decision model, released September 2026. It is **not an LLM** and
  does not generate text. It takes a `state` and typed questions and returns calibrated probabilities. The
  three question types:
  * **`choice`**: one of 2-255 labelled options.
  * **`noul`**: a yes/no probability.
  * **`score`**: 2-10 ordered levels, each written as a concrete situation.

  Questions are answered independently and in parallel.
* **Limits.** 64k tokens across the state and all questions; 32k for the state plus the longest question. The
  compiler keeps the state within 24k tokens, and the client refuses to send anything over the limits.
* **Not trainable.** The weights are closed and there is no fine-tuning; it works zero-shot over the criteria
  we write. Human judgement reaches it through the **heuristics** in the choice instructions and the
  **precedents** in the state (§7).
* **Access.** OpenRouter lists it as `typesafe/jev-1.13`. Chat completions answers 400 for it, so the call goes
  to `POST {JEV_BASE_URL}/systemone`. The base URL defaults to `https://openrouter.ai/api/v1` with
  `OPENROUTER_API_KEY`, or you can set `JEV_BASE_URL=https://api.typesafe.ai/v1` with a TypeSafe key in
  `JEV_API_KEY`. `typesafe/jev-router` is a chat model router, not this.
* **Unverified:** the response field names. `parse_response` accepts every variant the sources show.
  `scripts/verify_jev.py` makes one call so the real shape can be pinned.

## 4. The planner's output and the Jev request

The `DecisionPacket` (`ripple/incident/models.py`) is assembled in code from the agents' replies:

| Field | From | Meaning |
|---|---|---|
| `event` | webhook | `{id, kind, summary, source, received_at, raw}` |
| `evidence[]` | orchestrator | `{id: E1.., from_agent, claim, node_ids[], confidence: fact/ballpark/synthetic/unknown}` |
| `analysis` | analyst | `{impact_summary, metrics[{name, value, unit, basis_evidence_ids}], time_to_impact_hours, affected_node_ids, assumptions}` |
| `comms[]` | comms | `{id: C1.., recipient_role, recipient_node_id, channel, subject, body, purpose, required_by_option_ids}` |
| `decision_groups[]` | planner | `{id, question, mode: exclusive/independent, options[]}`. **The planner chooses the mode per group** |
| `options[]` | planner | `{id, title, action_kind (free text), steps, reversible, time_to_effect_hours, cost_estimate, risk, evidence_ids, alternative_to, comms_ids, is_wait}` |

`ripple.decide.compile.decision_request` turns it into:

| Packet | Jev question | id |
|---|---|---|
| an exclusive group | one `choice`; criteria = each option rendered with steps, reversibility, time, cost, risk and the evidence it rests on; instructions = the group's question + the human heuristics | `group__<gid>` |
| an option of an independent group | one `noul`; true = "warranted now", false = "unnecessary, premature or harmful" | `action__<oid>` |
| the event | one `score`, four levels (§5) | `priority` |

The state holds the event (marked as untrusted webhook data), the evidence, the analysis, the drafts, the
options and the 2-3 nearest precedents. When it runs over budget, the precedents are dropped first, then the
message bodies. `eval/decisions/scenario_felixstowe_fire.json` is a full worked example, and
`python scripts/verify_jev.py --dry-run` prints the exact request compiled from it.

## 5. Priority and autonomy

Priority measures **how long the decision can wait for a person**, not how high the stakes are.

| Level | The criterion Jev scores against | Human |
|---|---|---|
| low | impact is more than a week away or small; nothing gets worse by waiting a day | queue |
| medium | impact within days; waiting a few hours for a person costs little | queue |
| high | impact within 24-48 hours; a person should decide today; hours of delay narrow the options | queue |
| critical | the options are disappearing within hours: physical loss in progress, capacity or stock that others will take, perishable goods; waiting for approval makes the decision moot | **none** |

Policy (`ripple/decide/policy.py`; thresholds in `.env`):

* **auto** when Jev's top level is `critical` and P(critical) >= `RIPPLE_AUTO_PRIORITY_MIN` (0.5).
* In an auto event:
  * Jev's top option in each exclusive group is `auto_approved`. A winning wait option is a hold, approved
    only if `RIPPLE_AUTO_APPROVE_WAIT`.
  * The other options in that group are `not_selected`.
  * An independent action is `auto_approved` when P(yes) >= `RIPPLE_AUTO_NOUL_MIN` (0.6), and `pending`
    otherwise.
* Otherwise every option is `pending`, with Jev's probability shown next to it.

"Execute" means the option is marked approved, and its **live impact** is shown: the graph nodes it touches as
they are now, the metrics its evidence sizes, the messages it sends, and when it takes effect. The impact is
recomputed from the graph on every read.

## 6. Decisions moved out of the LLM agents

| Would have been an LLM decision | Is instead |
|---|---|
| which experts to ask | a Jev `noul` per approved role (>= `RIPPLE_EXPERT_RELEVANCE_MIN`; if none qualifies, Jev's most relevant) |
| when to stop questioning | a Jev `noul` after each round (>= `RIPPLE_EVIDENCE_SUFFICIENT_MIN`), plus the round cap |
| which option, and how urgent | the Jev decision request (§4, §5) |

The orchestrator still decides *what to ask*, because writing a question is generation. The LLM agents never
see a probability or a verdict (`tests/test_incident.py` checks this).

## 7. How humans decide: precedents

`ripple/decide/precedents.jsonl` holds 9 documented disruptions:
* Philips 2000, as two records: Nokia, which worked, and Ericsson, a negative example
* Aisin 1997
* Renesas 2011
* the Ever Given in 2021
* the Red Sea in 2023
* the Baltimore bridge collapse in 2024
* the Ocado Andover fire in 2019
* the Thailand floods in 2011

Each record holds what was known at the time, the options, the choice, the outcome, the priority in hindsight
and the heuristics it supports. Each also has a `verify` list of figures to check against primary sources.

* **In the state.** `precedents.nearest` retrieves by token overlap, and keeps a positive/negative pair about
  the same event together.
* **As heuristics.** `precedents.HEURISTICS` go into every choice question's instructions.
* **As calibration.** `decide/calibrate.evaluate` compiles each case as the decision stood at the time, with
  no outcome and no choice. It then checks whether Jev picks what worked (or avoids what failed) and the
  hindsight priority. The heuristics came from these same cases, so agreement is an upper bound. Add held-out
  cases for an honest number.

## 8. Code map

| Path | What |
|---|---|
| `ripple/decide/jev.py` | `JevClient`, `JevRequest`/`JevQuestion`/`JevAnswer`/`JevResult`, pre-send checks, `parse_response`, `set_jev_client` |
| `ripple/decide/compile.py` | `decision_request`, `relevance_request`, `sufficiency_request`, `precedent_request`, `render_state`, `PRIORITY_LEVELS` |
| `ripple/decide/policy.py` | `apply(packet, result, qmap, thresholds) -> Outcome` |
| `ripple/decide/precedents.py` + `.jsonl` | the cases, `nearest`, `render`, `HEURISTICS`, `problems` |
| `ripple/decide/calibrate.py` | the precedent eval |
| `ripple/incident/models.py` | `EventRecord`, `OrchestratorTurn`, `Exchange`, `EvidenceReport`, `AnalystReport`, `CommsReport`, `PlannerTurn`, `DecisionPacket` |
| `ripple/incident/agents/` | `orchestrator`, `analyst`, `comms`, `planner`, and `prompts/*.md` (product behaviour) |
| `ripple/incident/validate.py` | the referential checks on every agent reply |
| `ripple/incident/store.py` | `_Incident`, `_Option`, `_JevDecision`, `_Approval`, `(:_Incident)-[:CONCERNS]->(n)`; queries in `graph/queries/incident*.cypher`, `jev_decision*`, `approval*`, `nodes_by_ids` |
| `ripple/incident/pipeline.py` | `receive`, `run`, `choose_experts`, `consult`, `analyse_and_draft`, `assemble`, `decide`, `approve`, `reject`, `impact`, `detail` |
| `ripple/api/routes_incidents.py` | the webhook and the incident API |
| `ui/src/pages/Incidents.tsx` | report an event, follow the run live, see Jev's probabilities, approve/reject, live impact |
| `scripts/verify_jev.py`, `eval/run_jev_precedents.py` | one real Jev call; the precedent eval |
| `tests/test_jev.py`, `test_decide.py`, `test_incident.py` | deterministic (transport stubs only) |
| `tests/test_incident_live.py` | `-m llm` prompts, `-m jev` Jev, `-m "llm and jev and slow"` a whole incident |

Steps stream on the existing `/api/onboarding/stream` with `stage: "incident"` and `data.incident`. They are
also stored as `_AgentStep` nodes, under the agents `webhook`, `pipeline`, `orchestrator`, each expert's
name, `analyst`, `comms`, `planner`, `jev` and `user`.

## 9. Decisions taken where the owner had not specified (change freely)

1. **Thresholds** are global (env), not per tenant: 0.5 for priority, 0.6 for an action, 0.5 for relevance and
   0.6 for sufficiency.
2. **After an auto-approval** there is no notification. The audit trail is the `_Approval` nodes (actor
   `jev-policy`), and a person can **undo** any auto-approved option (reject) from the UI.
3. **A winning wait** in a critical event is approved as a hold (`RIPPLE_AUTO_APPROVE_WAIT=true`).
4. **The webhook** accepts any JSON object with `summary` (or `text`, `message` or `description`). `kind`/`type`,
   `source` and `received_at` are optional, and the whole body is kept as `raw`. `RIPPLE_WEBHOOK_SECRET`, when
   set, is checked against `X-Ripple-Webhook-Secret`.
5. **Re-run** creates a new incident from the same event rather than overwriting the old one.
6. **No external execution.** An approved option is marked approved and its impact is shown; no message is
   sent and no system is called.

## 10. Known gaps

* The Jev response shape is unverified (§3).
* `nodes_by_ids` and `incident_concerns_link` match unlabelled nodes, which scans. Incidents name few ids, so
  this is fine at demo scale. The fix is the same label grouping `instance_merge_edges` uses.
* The step stream is per tenant, not per incident. Agent steps without `data.incident` show on every incident's
  trail in the UI.
* The precedent figures carry `verify` lists. Check them before quoting them anywhere.

## 11. What to run (nothing below has been run yet)

```bash
bash scripts/setup_env.sh                                   # if the venv is not there
.venv/bin/ruff check ripple tests scripts eval              # lint
.venv/bin/pytest -q                                         # deterministic: includes test_jev, test_decide, test_incident
.venv/bin/python scripts/verify_jev.py --dry-run            # the exact Jev request for the scenario
.venv/bin/python scripts/verify_jev.py                      # one real Jev call -> pin reference/JEV_VERIFIED.md
.venv/bin/pytest -q -m llm -k incident                      # the incident prompts against a real LLM
.venv/bin/pytest -q -m jev                                  # Jev answers our requests
.venv/bin/python eval/run_jev_precedents.py                 # how often Jev agrees with what worked
.venv/bin/pytest -q -m "llm and jev and slow"               # one whole incident, live
cd ui && npm run build                                      # type-check and build the Incidents page
```

The webhook by hand, against a running API with an onboarded tenant:

```bash
curl -X POST "localhost:8000/api/events/<tenant_id>?wait=true" -H 'Content-Type: application/json' \
  -d '{"kind": "site_incident", "source": "site-alerts", "summary": "Fire reported at the Felixstowe bonded warehouse, unit 4. Bays C-F may be affected; no access."}'
```
