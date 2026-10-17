# Jev: what is verified

The counterpart of `FALKORDB_VERIFIED.md` for Jev, TypeSafe's decision model. It wins over the design doc
(`docs/m8_decision_pipeline.md`) and over third-party guides.

## Status: request shape from sources, response shape NOT verified

The build container could not reach openrouter.ai or docs.typesafe.ai (network policy), so nothing here has
been checked against a live call yet.

**Agreed across sources (used as-is in `ripple/decide/jev.py`):**

* `POST {base}/systemone`, `Authorization: Bearer <key>`. Base `https://openrouter.ai/api/v1` (OpenRouter key)
  or `https://api.typesafe.ai/v1` (TypeSafe key). Chat completions answers 400 for Jev.
* Body: `{"model", "state", "questions": {"<id>": {"type": "choice"|"noul"|"score", "instructions",
  "criteria"}}}`. Choice criteria are `{label: description}` (2-255); score criteria are an ordered list of
  2-10 levels; noul criteria are optional `{"true", "false"}`.
* Limits: 64k tokens for the state plus all questions; 32k for the state plus the longest question.
* OpenRouter model ids: `typesafe/jev-1.13`, pinned `typesafe/jev-1.13-20260917`; 1.14 may be out.

**Unverified (the parser accepts every variant seen):**

* Where the answers sit: `answers.<id>`, `choices.<id>`, `results`, or a list of `{id, ...}`.
* A choice answer: `{"choice", "probabilities": {label: p}, "confidence"}`. Are probabilities keyed by label,
  and are they a full distribution?
* A noul answer: a bare number, `{"noul": p}`, `{"probability": p}`, or a boolean plus `confidence`.
* A score answer: is it keyed by the level text we sent (`"critical: the options..."`), by the text before the
  colon, or by index?

## To verify (one call)

    .venv/bin/python scripts/verify_jev.py --dry-run      # the exact request, no network
    .venv/bin/python scripts/verify_jev.py                # the real call; saves artifacts/jev_runs/verify-*.json

Paste the raw response below, then narrow `parse_response` to that shape and rewrite
`tests/test_jev.py::test_the_documented_shape_parses` to use the real body.

```json
(raw response goes here)
```
