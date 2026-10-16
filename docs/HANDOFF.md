# Handoff: questions for you, and what is still open

Written at the end of the autonomous v2 build session (2026-10-15). `plan.md` §11 says what was built;
`docs/KNOWN_ISSUES.md` lists every deviation and everything unverified. This file is the short version of what
I need **from you**, in the order I would want it answered.

---

## 1. Decisions I made that are yours to overrule

I did not stop to ask, because the plan said not to pause. Each of these is a real choice, and each is cheap to
reverse now and expensive later.

### 1.1 Query templates, not a base-concept layer (plan §9.1.1)

You deferred this one. I needed an answer to ship M5, so I took option **(b) templated queries**: the Cypher
text stays in `graph/queries/*.cypher` with `{placeholders}`, and `Q(name, label=...)` fills them after
`validate_spec` has accepted the label, through one guarded function (`graph/queries.ident`).

It settles the six read-only tools and nothing else. **The question you deferred is still open for analytics**:
what does a blast-radius query look like over types nobody wrote by hand? My instinct, for what it is worth,
is a thin **base-concept layer** — the ontology agent tags each generated type with one of a dozen fixed
concepts (`Party`, `Material`, `Location`, `Movement`, `Demand`, `Obligation`, `Event`), and the hand-written
analytics are written against the tags rather than the labels. The spec already has a `tags` field for exactly
that and nothing populates it yet. **This is the one decision I would most like from you before M8.**

### 1.2 Uploads are parsed with the standard library (plan §5)

You offered two options: add `openpyxl`/`pypdf`/`python-docx`, or route binaries through the Claude Code
bridge. I took **neither**. `CLAUDE.md` says not to add dependencies and the vendored set is what makes the
offline build work, and handing a file to the model is both slow and a prompt-injection surface. So `.docx`
text comes out of its XML and `.pdf` text out of its content streams, both with the stdlib.

The cost is honest and visible: a **scanned PDF is refused** with a message telling the user to upload the
text instead, and **`.xlsx` only works if `openpyxl` happens to be installed** (it is not vendored), otherwise
it says "export the sheet as CSV". If you would rather have those two work properly, adding the three
libraries is a ten-minute change — tell me and I will do it.

### 1.3 The brief is patched in place within a version

The plan said artifacts are versioned and never overwritten. Taken literally that is a brief version per
interview turn, which makes the history unreadable. I version it on a **boundary** instead: the open version is
patched turn by turn, and a new version is cut when the current one is approved or has been flagged stale by a
jump back. Same for the ontology draft. Say the word if you want per-turn versions.

### 1.4 There is still no auth (plan §9.1.3)

Unchanged from the plan, but worth stating plainly: the tenant id is in a cookie, and **anyone who can reach
the API can put any tenant id in a header and read that tenant**. That is fine for a single-user local app and
a demo. It is not fine the moment this is on a public URL with two companies in it. `render.yaml` deploys it
to a public URL.

---

## 2. Questions I could not answer from the plan

### 2.1 What happens after onboarding is genuinely blank (plan §10)

The plan gates M8 on your spec, so I stopped. But it leaves the product in an odd state: a company finishes
onboarding, approves its experts, and lands on... an Experts page where it can ask one role one question at a
time. There is no control tower, no incident, no action, no memory. The `mem_<id>` graph exists and is empty.

I think the smallest honest M8 is **one page**: ask a question, the right expert is picked (or several are and
their answers are composed), and the answer carries the graph path it came from. That is Track 01 and 03 on a
generated ontology and needs no new concepts. Everything v1 had — incidents, blast radius, the action queue
with human approval, playbooks that learn — is a second step that needs the §1.1 decision first.

### 2.2 The data pack has no transactions, so the experts have nothing to analyse

This is the most interesting thing the verified live run showed, and I could not decide it for you.

The data agent asked for suppliers, components, sites, lanes, customers and commercial terms. It never asked
for an order or a shipment — reasonably, because the interview was about the shape of the business. The
ontology agent then declared `Order`, `Shipment` and `RiskEvent` anyway, from the brief's *pains*, which is
also right: the pains are the requirements.

Result: three of the six generated roles were asked a playbook question and answered, in effect, *"the graph
holds no orders; I am not going to make up numbers"* — citing the customers and sites that do exist. The
prompts worked exactly as written. But it is the demo's ceiling: a disruption-impact analyst with no orders
can only explain what it would do.

Two ways out, and they are not exclusive:

1. **The data agent asks for a sample of live transactions** — "paste or upload fifty open orders" — so the
   operational roles have something to stand on. More honest about what a real deployment needs, and more
   work for the user.
2. **The expert generator scopes each playbook to types that have instances**, and says plainly which
   questions will only work once the data is connected. Cheaper, and it makes the gap visible instead of
   surprising.

I lean towards (2) now and (1) as part of M8, where "connect your ERP" belongs anyway. Your call.

### 2.3 Agent memory is scaffolded but unused

`mem_<id>` has platform indexes for `_Episode`, `_Fact`, `_Conversation`, `_ConvMessage` and nothing writes
them, because the plan puts memory in the main application. Track 02 is one of the three tracks you entered.
If the submission needs a memory story, the cheapest real one is: **record each expert answer as an episode,
and each thing the user corrects as a temporal fact that supersedes what the graph said**. That is a day's
work on top of what exists and it would be genuinely used rather than demonstrated.

### 2.4 Is the demo meant to run live, or from a recording?

A live onboarding is the whole point, and it takes **about ten minutes and real money** (the verified run:
25 Claude Opus calls, 10m33s, in `artifacts/llm_runs/20261015-204539`). For a judged demo that is a lot of dead air. I added
`scripts/seed_from_run.py`, which replays a *recorded* real run into a database you keep, so you can click
through finished output instantly — and `scripts/demo.py`, which runs it live in the terminal. Which one do
you want to be the primary? If it is the recording, I would record one good run and commit its artifacts.

### 2.5 Which model, and at what effort?

Everything was built and tested against the **Claude Code CLI on this machine's login** at `--model opus`,
effort `medium`. I have not measured whether `sonnet` is good enough for the interviewer and the data agent
(it probably is) and `opus` only for the ontology and expert agents (where the reasoning actually shows). That
would cut the cost of a demo run by most of it. Worth an hour if cost matters.

---

## 3. Problems I know about and did not fix

### 3.1 Not verified at all (the full list is in `docs/KNOWN_ISSUES.md`)

* **Docker.** `Dockerfile`, `docker-compose.yml` and `render.yaml` are updated for v2 and **never built** —
  the sandbox has no Docker. The first `docker compose up --build` will probably need one or two fixes.
* **Remote mode.** v2's suite has only run against the embedded engine. It is written to run against a server
  (`RIPPLE_DB_MODE=remote .venv/bin/pytest -q`) and v1's suite did, so I expect it to pass — but I have not
  seen it.
* **The bridge path.** `CLAUDE_CODE_BRIDGE_URL` is unit-tested against a fake transport, never across a real
  container boundary. This is how Docker gets an LLM, so it matters for the demo.
* **OpenRouter and the Anthropic API** live. Request translation and response parsing are tested; no real call
  was made (no key here).
* **The UI clicked by a person.** All four pages now render in headless Chromium against a real tenant and
  `docs/img/*` are those screenshots, so the README is honest. But no *interaction* was automated: filling a
  form, approving the ontology, editing a prompt and asking an expert are covered through the API and the
  tests, not through the browser. That is the gap most likely to hold a surprise.

### 3.2 The tag could not be pushed

`git tag v1-dataco` exists locally; `git push origin v1-dataco` is refused with **HTTP 403** by this session's
GitHub access (branch pushes work, tag pushes do not). v1 is safe either way — it is commit `04d4bd4`, on
`origin/main` and in this branch's history. Push the tag yourself when convenient:
`git push origin v1-dataco`.

### 3.3 Things that will annoy a real user

* **A turn is synchronous and can take 30–60 seconds.** The live step trail makes it legible, but there is no
  streaming of the reply text itself (the structured-output call has no partial parse). A typing indicator and
  a step feed is what you get.
* **`describe_ontology` is 40 ms and every expert calls it first**, every question. It should be cached per
  approved spec version.
* **The expert runtime has no memory between questions.** Each `ask` is a fresh loop. Fine for one question,
  wrong for a conversation.
* **Re-approving an ontology wipes and reloads all instance data.** Correct, and it throws away anything that
  arrived by another route. There is no other route yet, so it is safe today and a trap tomorrow.
* **File→field mapping is wired but untested by a human.** The agent proposes mappings
  (`DataTurn.file_mappings`), and `POST /api/onboarding/forms/{id}/map` confirms one: it re-reads the stored
  upload and writes the column's values as answers with `source: "file"` (a whole repeating group in one
  call). Covered by deterministic tests. What I have *not* seen is a model proposing a mapping against a real
  upload in a live run — the verified run's persona typed its answers.

---

## 4. What I would do next, in order

1. **Answer §1.1** (base concepts vs richer templates) — everything analytical waits on it.
2. **Spec M8's one page** (§2.1): ask a question, get an answer with its graph path.
3. **Build the file→field confirm step** (§3.3) — the only promised-and-missing piece of the plan.
4. **Run `docker compose up --build` once** and fix what it finds.
5. **Record one good live run**, commit its artifacts, regenerate the screenshots from it, and point the README
   at those.
6. **Then** memory (§2.3), if Track 02 needs more than the plan gives it.

---

## 5. How to check my work in twenty minutes

```bash
bash scripts/setup_env.sh
.venv/bin/pytest -q                                   # 178 deterministic tests, no network, ~13s
.venv/bin/python scripts/verify_falkordb.py            # every FalkorDB behaviour v2 relies on
.venv/bin/pytest -q -m llm -k prompt                   # 12 live calls: every prompt against its schema (~6 min, real spend)
.venv/bin/uvicorn ripple.api.app:app                   # then http://localhost:8000 and type a company name
```

Then read, in this order: `ripple/onboarding/agents/prompts/*.md` (the product),
`ripple/onboarding/models.py` (the contracts), `ripple/onboarding/validate.py` (what can be rejected and why),
and `ripple/graph/queries.py:ident` (the one place a model-authored string reaches Cypher).
