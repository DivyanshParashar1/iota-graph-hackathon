# M8 design: the incident pipeline and Jev

Status: **draft for review**. Nothing here is built yet. It records the owner's description (2026-10-17) and
the research behind the Jev contract. When this is approved it moves into `plan.md` as §10.

## 1. The one rule

**Only Jev decides.** Every other agent generates: it collects evidence, writes reports, drafts messages, and
proposes options. None of them picks. Any step that would be a decision inside an LLM agent is instead a Jev
question (see §6). The LLM agents' job is to make the `state` Jev reads complete, sourced and short.

## 2. Flow

```
 webhook (POST /api/events/{tenant})  ── an event is reported
        │
   ORCHESTRATOR (LLM) ── hub and spoke, experts never talk to each other
        │  asks ─────► expert A ─┐
        │  asks ─────► expert B ─┤  _ExpertRole agents (M5 runtime), answering from the tenant graph
        │  follow-up ► expert A ─┘
        │  loops until "enough evidence"  (stop = a Jev question, §6)
        ▼
   EVIDENCE REPORT  (everything the experts said, with node ids)
        │
   ┌────┴─────┐  parallel, each gets the full report
 ANALYST    COMMS
 impact,    one drafted message per stakeholder
 numbers    (owner, contract clause, what we ask of them)
   └────┬─────┘
        ▼
   PLANNER (LLM) ── proposes decision groups, options and alternatives. Free-form actions, written the way the
        │           industry normally solves this kind of problem. Does not rank or choose.
        ▼
   DecisionPacket  (schema in §4, example in eval/decisions/scenario_felixstowe_fire.json)
        │  compiled deterministically (no LLM) into one Jev request
        ▼
   JEV  ── P(option) per group, P(yes) per independent action, priority distribution for the event
        │
   priority == critical ──► auto-approve, execute (mark approved), show live impact
   otherwise           ──► human approval queue, with Jev's probabilities shown next to each option
```

## 3. What Jev is (researched 2026-10-17)

* **Jev** is TypeSafe AI's "System One" decision model, released September 2026. It is **not an LLM** and does
  not generate text. It takes a `state` (text or JSON) and a set of typed questions, and returns calibrated
  probabilities. TypeSafe's claim is that 0.8 means "right about 80% of the time". We should check that on
  our own precedents (§7) rather than take it on trust.
* **Question types.** **`choice`** picks one of up to 255 labelled options and returns a probability for
  each. **`score`** places the state on an ordered scale of 2-10 levels, each written as a concrete
  situation. **`noul`** is a yes/no probability, optionally with explicit true and false conditions. Every
  question is answered independently and in parallel against the same state, so adding questions costs
  almost no extra latency.
* **Limits.** 64k tokens across the state and all questions; 32k for the state plus the longest single
  question. Output tokens are free and input costs about $0.042 per million tokens (vendor figure).
* **Not trainable by us.** It is closed-weight, there is no fine-tuning, and it is zero-shot over the criteria
  we write. So "teaching Jev how humans decide" means two things: (a) the **criteria text** encodes human
  decision heuristics, and (b) the **state** carries the closest **precedents**. The precedent set doubles as
  our calibration/eval set.
* **OpenRouter: yes.** It is listed as `typesafe/jev-1.13` (pinned build `typesafe/jev-1.13-20260917`; 1.14
  may now be out). It is **not** served through chat completions, which returns a 400 for it. Use
  `POST https://openrouter.ai/api/v1/systemone` (TypeSafe-compatible) or OpenRouter's alpha decisions API.
  TypeSafe's own endpoint is `POST https://api.typesafe.ai/v1/systemone`. `typesafe/jev-router` is a
  different product: a chat-format model router. We don't want it.

**Unverified.** The cloud container that wrote this could not reach openrouter.ai or docs.typesafe.ai
(network policy). The request shape below agrees across several third-party guides. The exact **response**
field names (`answers.<id>.choice` / `.probabilities` / `.confidence`) differ between sources. Before writing
the client, make one real call and pin the shape in `reference/JEV_VERIFIED.md`, in the same way that
`reference/FALKORDB_VERIFIED.md` pins FalkorDB.

Request, as we will send it:

```json
POST /v1/systemone
{
  "model": "typesafe/jev-1.13-20260917",
  "state": "<rendered DecisionPacket + precedents, <= ~24k tokens>",
  "questions": {
    "g1_fulfilment": { "type": "choice", "instructions": "...", "criteria": { "opt_a": "...", "opt_b": "..." } },
    "a_notify_insurer": { "type": "noul", "instructions": "...", "criteria": { "true": "...", "false": "..." } },
    "priority": { "type": "score", "instructions": "...", "criteria": ["low: ...", "medium: ...", "high: ...", "critical: ..."] }
  }
}
```

## 4. The planner's output: `DecisionPacket`

The planner is the last LLM. It emits a pydantic-validated `DecisionPacket`, and a pure function
`compile_jev_request(packet, precedents)` turns that into the request above. Fields:

| Field | Meaning |
|---|---|
| `event` | `{id, received_at, source, kind, summary, raw}` from the webhook |
| `evidence[]` | `{id, from_agent, claim, node_ids[], confidence: fact/ballpark/synthetic}` — every claim the options rest on |
| `analysis` | the analyst's report: `{impact_summary, metrics[{name, value, unit, basis_evidence_ids[]}], time_to_impact_hours}` |
| `comms[]` | the comms agent's drafts: `{id, recipient_role, recipient_node_id, channel, subject, body, required_by_option_ids[]}` |
| `decision_groups[]` | `{id, question, mode: "exclusive" \| "independent", options[]}` — **the planner chooses the mode per group** (owner's answer 8) |
| `options[]` | `{id, title, action_kind (free text), steps[], reversible: bool, time_to_effect_hours, cost_estimate, risk, evidence_ids[], alternative_to: option_id \| null, comms_ids[]}` |

Mapping to Jev:

* An `exclusive` group becomes **one `choice` question**. Its options are the criteria, and each criterion
  text is the option's title, steps, cost, time to effect and reversibility. The planner always adds a "wait
  and gather more information" option. Holding still is a real choice, and it gives Jev somewhere to put
  probability when nothing else is supported.
* Each option in an `independent` group becomes **one `noul` question**. The true condition is "this should be
  done now given the state" and the false condition is "this is unnecessary, premature or harmful". Several
  options can come out true.
* An `alternative_to` link is for display only (a fallback shown under its primary). It does not create a
  question, because the fallback is already an option in the same `choice`.
* The event priority is **one `score` question** with four levels (§5).

## 5. Priority and autonomy

Priority measures **how long the decision can wait**, not how high the stakes are (owner's answer 10).

| Level | Concrete situation (this is the criteria text Jev scores against) | Human in the loop |
|---|---|---|
| low | Impact is more than a week away, or small, and nothing gets worse by waiting a day. | queue |
| medium | Impact within days. Waiting a few hours for a person costs little. | queue |
| high | Impact within 24-48h. A person should decide today. A delay of hours narrows the options. | queue, flagged |
| critical | The options are disappearing in hours: physical loss in progress (fire, flood), a capacity or slot that competitors will take, perishable stock. Waiting for approval would make the decision moot. | **auto-approve** |

Proposed policy, in config and not a model: **auto-approve when Jev's top priority level is `critical` and
P(critical) >= 0.5.** Then approve the top option of each `choice` group and every `noul` action with
P(yes) >= 0.6. Everything else, including low-probability options in a critical event, goes to the queue.
"Execute" means mark it approved and show its live impact on the graph (owner's answer 11).

## 6. Decisions hidden inside the LLM agents, moved to Jev

The rule in §1 catches three places where an LLM would otherwise decide:

1. **Which experts to ask.** One `noul` per approved expert: "is this role's mandate relevant to this event?"
   The orchestrator writes the questions it will put to the experts. Jev's answers choose who gets them.
2. **When the Q&A loop stops.** After each round, one `noul`: "is the evidence sufficient for the planner to
   propose actions?" Plus a hard cap on rounds and spend, so the loop always ends.
3. **Priority.** It is assigned only by Jev (§5), never by the analyst.

The orchestrator still decides *what to ask* (it generates the questions). It does not decide *whom* or *when
to stop*.

## 7. How humans decide: precedents and heuristics

`eval/decisions/precedents.jsonl` holds documented real disruptions. Each record has what was known at the
time, the options the decision-makers had, what they chose, how it turned out, and the heuristic it
illustrates. It has two uses:

* **In the state.** The 2-3 nearest precedents (by event kind) are rendered into Jev's state as "how
  experienced operators handled similar events".
* **As the eval.** Compile each precedent into a Jev request (a choice over the options considered, and a
  priority score) and check whether Jev favours the choice that worked (Nokia, not Ericsson). That is how we
  check calibration on our own data, as §3 says we must.

The heuristics the precedents support go into the `instructions` text of every choice question:

1. **Escalate on weak signals.** Do not anchor on the affected party's first estimate of the damage.
   (Philips/Nokia/Ericsson 2000)
2. **Secure scarce capacity before competitors do.** Allocation is first come, first served. (Nokia 2000,
   Thailand floods 2011, Red Sea 2023)
3. **Prefer reversible actions while uncertainty is high**, and commit to irreversible ones only when the
   expected disruption is longer than their cost. (Ever Given 2021: most carriers waited; Red Sea 2023:
   carriers rerouted)
4. **Use pre-qualified alternatives before new ones.** Another plant, warehouse or port you already use beats
   a new supplier. (Ocado Andover 2019, Baltimore 2024)
5. **When there is no alternative, help the source recover.** (Aisin 1997, Renesas 2011)
6. **Protect the customers who would suffer most, and tell everyone early.**

## 8. Worked scenario

`eval/decisions/scenario_felixstowe_fire.json` is the scenario for **Harbour Coffee Roasters**, the second
company recorded in `docs/HANDOFF.md`, which uses bonded warehousing at Felixstowe. A fire is reported at the
bonded warehouse. The file contains the webhook payload, the experts the orchestrator consulted, the planner's
`DecisionPacket`, the compiled Jev request, and the policy outcome for each possible priority. The entity names
are **illustrative**: they follow the brief's shape, but the real ids come from the tenant graph at run time.

## 9. Fit with the repo

* Jev is not an LLM, so it does not go through `ripple/llm/`. It needs a new `ripple/decide/jev.py` client with
  one method, `decide(request) -> JevAnswer`, on `httpx`, which is already pinned. No new dependency.
* "No fakes" still holds. Route tests stub the HTTP transport at the boundary, like `tests/conftest.StubClient`.
  There is no scripted Jev. Live tests are `-m jev`.
* The webhook, the incident, options, Jev answers and approvals become platform nodes (`_Incident`,
  `_Option`, `_JevDecision`, `_Approval`), with queries in `graph/queries/incident.cypher`.
* Keys: `OPENROUTER_API_KEY` is already in config. Add `RIPPLE_JEV_BASE_URL` and `RIPPLE_JEV_MODEL`.

## 10. Still open

1. Should the auto-approve thresholds (0.5 for priority, 0.6 for a noul action) be global, or set per
   tenant?
2. On a critical event, should a human still get a notification with an undo window, or is an audit log
   enough?
3. Does the "wait" option in an exclusive group get auto-approved when it wins in a critical event? (Proposed:
   yes. It means "hold", and the event re-runs on the next webhook.)
4. Does the webhook accept any JSON with a free-text `summary`, or a fixed schema from specific feeds?
