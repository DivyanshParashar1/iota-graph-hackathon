# Quality rubric for the four onboarding agents

The deterministic suite proves the plumbing. This rubric is how a human judges the part no assertion can: did
the agents actually understand this company, and is what they built worth approving?

Score a recorded live run (`artifacts/llm_runs/<ts>/`, written by `.venv/bin/pytest -m llm -k full_onboarding`)
or a session you ran by hand. Each item is 0 / 1 / 2: **0** = no, **1** = partly, **2** = yes. Record the
score, the run id and one sentence of evidence per item — a score with no quote is not a score.

An LLM judge may fill the evidence column first (`--judge`, below); a human signs the total. Both are recorded.

## 1. Interviewer (max 16)

| # | Item | Evidence to quote |
|---|---|---|
| 1.1 | The opening turn asks a handful of questions, not a wall, and they are the right first questions for this business | the opening `reply` |
| 1.2 | Follow-ups respond to what was said, rather than walking a fixed list | two consecutive turns |
| 1.3 | It never asks something already answered | the checklist's `resolve` ops vs the questions asked after them |
| 1.4 | It picks up the company's own vocabulary and records what it means | `brief.vocabulary` |
| 1.5 | The checklist grows where the answers opened new ground (a tier-2 risk, a second site) and shrinks as things are answered | `checklist_ops` across turns |
| 1.6 | It asked for a ballpark rather than pressing for a figure nobody has to hand | any turn mentioning "ballpark" / "roughly" |
| 1.7 | It stopped at the right time — not after three turns, not after thirty | `done_reason` and the turn count |
| 1.8 | The brief reads like this company, and a colleague could be briefed from it | `brief.json` as a whole |

## 2. Data agent (max 12)

| # | Item | Evidence to quote |
|---|---|---|
| 2.1 | Round 1 asks for the backbone — the entities and properties the ontology cannot do without | the first `FormSpec` |
| 2.2 | Lists of like things are repeating groups, not `supplier_1`, `supplier_2` | the group fields |
| 2.3 | Field types and units are right (days as integers, shares as percent, money as currency) | any numeric field |
| 2.4 | `help` text makes a field answerable without asking what it means | three fields at random |
| 2.5 | A later round is narrower and follows from the answers, rather than repeating round 1 | round 2 vs round 1 |
| 2.6 | It invented no values of its own anywhere (only `Synthesize` may, and it badges them) | every answer's `source` |

## 3. Ontology agent (max 14)

| # | Item | Evidence to quote |
|---|---|---|
| 3.1 | The types are this company's concepts in this company's words | the type labels and descriptions |
| 3.2 | Properties that belong to a *pairing* are on the relationship, not copied onto a node (lead time on `SUPPLIES`) | the relationship properties |
| 3.3 | No type exists that the data pack cannot populate, and nothing in the data pack has nowhere to go | `coverage` |
| 3.4 | Synonyms are merged and the rationale says so | `rationale` |
| 3.5 | The model would answer the questions the brief's `pains` describe | pains vs types/relationships |
| 3.6 | It is the size of the business — not three types, not a hundred | the type count |
| 3.7 | The instance data loaded from the data pack is right: real entities, no invented ones, numbers matching the answers | the loaded counts vs the answers |

## 4. Expert generator (max 12)

| # | Item | Evidence to quote |
|---|---|---|
| 4.1 | The roles are the ones *this* chain needs, and a role the company has no data for is absent | the role list and `dropped` |
| 4.2 | Each justification names the types it reasons over and the problem it solves | each `justification` |
| 4.3 | No two roles overlap; a boundary case is assigned explicitly | the mandates read together |
| 4.4 | Each system prompt would work with no further editing: identity, mandate, how to reason, what a good answer is, what not to do | one prompt in full |
| 4.5 | Each playbook question is one a real person would ask in those words | the playbooks |
| 4.6 | Asked a playbook question, the role answered from the graph, cited ids that exist, and invented no numbers | the answer and its `ids` |

## 5. The product around them (max 8)

| # | Item | Evidence to quote |
|---|---|---|
| 5.1 | Every answer, form and step survives a reload mid-answer | reload the browser during a turn |
| 5.2 | Going back a stage marks the right things stale and nothing is silently rewritten | the stage rail after a jump |
| 5.3 | "Where did this number come from?" lands on the exact field or column | the provenance panel |
| 5.4 | Synthetic values are visibly synthetic everywhere they appear | a synthesized form and the loaded nodes |

**Total: 62.** A run worth demoing scores ≥ 50 with no zero in 2.6, 3.7, 4.2, 4.6 or 5.4 — those five are the
honesty items, and a zero in any of them means the product claimed something it had not earned.

## Running the judge

```bash
.venv/bin/pytest -m llm -k full_onboarding -s        # writes artifacts/llm_runs/<ts>/
.venv/bin/python eval/run_rubric.py --run <ts>       # LLM judge fills the evidence, writes <ts>/rubric.json
```

The judge is given the rubric, the run's artifacts and nothing else, and is told to quote rather than
summarise. Its scores are advisory: `rubric.json` has a `human` block to be filled in by the person who signs
it off.
