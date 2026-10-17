"""The Jev client. Jev is TypeSafe AI's "System One" decision model: it takes a `state` and typed questions
and returns calibrated probabilities. It does not generate text, which is why it is not an `LLMClient` and
never goes through `ripple/llm/`.

    POST {JEV_BASE_URL}/systemone
    {"model": "typesafe/jev-1.13", "state": "...", "questions": {"<id>": {"type", "instructions", "criteria"}}}

Question types: `choice` (one of up to 255 labelled options), `noul` (yes/no), `score` (2-10 ordered levels).
Limits: 64k tokens across the state and every question, 32k for the state plus the longest question. Chat
completions does not serve Jev (it answers 400), so this goes to the `systemone` route OpenRouter and TypeSafe
both expose.

**The response shape is not verified yet.** Third-party guides disagree on field names (`answers.<id>.choice`
vs `choices[<id>]`, `noul` as a bare number vs `{probability}`), so `parse_response` accepts each variant
seen and normalises it to `JevAnswer`. `scripts/verify_jev.py` makes one real call and prints the raw body;
pin what it shows in `reference/JEV_VERIFIED.md` and narrow the parser to it.

There is no fake Jev. Tests drive the real client over an `httpx.MockTransport` that returns a body the test
wrote (a stub at the transport boundary, like `tests/conftest.StubClient`).
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Literal, Protocol, runtime_checkable

import httpx
from pydantic import BaseModel, Field

from ripple.config import get_settings
from ripple.graph.queries import IDENT_RE
from ripple.llm.base import log_call

QuestionType = Literal["choice", "noul", "score"]
MAX_TOTAL_TOKENS = 64_000
MAX_PER_QUESTION_TOKENS = 32_000
MAX_CHOICE_OPTIONS = 255
MIN_LEVELS, MAX_LEVELS = 2, 10


class JevError(RuntimeError):
    """Jev could not answer: no key, transport, an over-budget request, or a body we could not read."""


def estimate_tokens(text: str) -> int:
    """A conservative token estimate (about 4 characters per token for English and JSON)."""
    return len(text or "") // 4 + 1


class JevQuestion(BaseModel):
    type: QuestionType
    instructions: str
    # choice: {option_id: description}; noul: {"true": ..., "false": ...} or None; score: ["level: ...", ...]
    criteria: dict[str, str] | list[str] | None = None

    def level_names(self) -> list[str]:
        """For a score question, the level keys: the text before the first ':' of each criterion."""
        if self.type != "score" or not isinstance(self.criteria, list):
            return []
        return [c.split(":", 1)[0].strip() for c in self.criteria]

    def labels(self) -> list[str]:
        if self.type == "choice" and isinstance(self.criteria, dict):
            return list(self.criteria)
        if self.type == "score":
            return self.level_names()
        return ["true", "false"]

    def body(self) -> dict:
        out: dict[str, Any] = {"type": self.type, "instructions": self.instructions}
        if self.criteria is not None:
            out["criteria"] = self.criteria
        return out


class JevRequest(BaseModel):
    model: str = ""
    state: str
    questions: dict[str, JevQuestion]

    def body(self, model: str) -> dict:
        return {"model": self.model or model, "state": self.state,
                "questions": {k: q.body() for k, q in self.questions.items()}}

    def problems(self) -> list[str]:
        """Everything that would make Jev reject this request, checked before it is sent."""
        errs: list[str] = []
        if not self.state.strip():
            errs.append("empty state")
        if not self.questions:
            errs.append("no questions")
        state_t = estimate_tokens(self.state)
        q_tokens = {k: estimate_tokens(json.dumps(q.body())) for k, q in self.questions.items()}
        if state_t + sum(q_tokens.values()) > MAX_TOTAL_TOKENS:
            errs.append(f"state + questions is about {state_t + sum(q_tokens.values())} tokens "
                        f"(limit {MAX_TOTAL_TOKENS})")
        if q_tokens and state_t + max(q_tokens.values()) > MAX_PER_QUESTION_TOKENS:
            errs.append(f"state + the longest question is about {state_t + max(q_tokens.values())} tokens "
                        f"(limit {MAX_PER_QUESTION_TOKENS})")
        for k, q in self.questions.items():
            if not IDENT_RE.match(k):
                errs.append(f"question id {k!r} is not a plain identifier")
            if q.type == "choice":
                n = len(q.criteria) if isinstance(q.criteria, dict) else 0
                if not 2 <= n <= MAX_CHOICE_OPTIONS:
                    errs.append(f"{k}: a choice needs 2-{MAX_CHOICE_OPTIONS} options, has {n}")
            if q.type == "score":
                n = len(q.criteria) if isinstance(q.criteria, list) else 0
                if not MIN_LEVELS <= n <= MAX_LEVELS:
                    errs.append(f"{k}: a score needs {MIN_LEVELS}-{MAX_LEVELS} levels, has {n}")
            if q.type == "noul" and q.criteria is not None and set(q.criteria) - {"true", "false"}:
                errs.append(f"{k}: noul criteria take only 'true' and 'false'")
        return errs


class JevAnswer(BaseModel):
    id: str
    type: QuestionType
    probabilities: dict[str, float] = Field(default_factory=dict)  # every label -> probability
    top: str = ""
    confidence: float | None = None

    @property
    def p_true(self) -> float:
        """For a noul: P(yes)."""
        return float(self.probabilities.get("true", 0.0))

    def p(self, label: str) -> float:
        return float(self.probabilities.get(label, 0.0))

    def ranked(self) -> list[tuple[str, float]]:
        return sorted(self.probabilities.items(), key=lambda kv: (-kv[1], kv[0]))


class JevResult(BaseModel):
    answers: dict[str, JevAnswer]
    model: str = ""
    usage: dict = Field(default_factory=dict)
    ms: float = 0.0
    raw: dict = Field(default_factory=dict)

    def __getitem__(self, qid: str) -> JevAnswer:
        return self.answers[qid]


# --------------------------------------------------------------------------- response parsing

def _num(x: Any) -> float | None:
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        try:
            return float(x)
        except ValueError:
            return None
    return None


def _prob_map(raw: Any, labels: list[str]) -> dict[str, float]:
    """Probabilities as {label: p}, from a dict keyed by label / full criterion / index, a list aligned with the
    labels, or a list of {label|option|value, probability|p} records."""
    out: dict[str, float] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            p = _num(v if not isinstance(v, dict) else v.get("probability", v.get("p")))
            if p is None:
                continue
            key = _match_label(str(k), labels)
            if key is not None:
                out[key] = p
    elif isinstance(raw, list):
        for i, item in enumerate(raw):
            if isinstance(item, dict):
                name = item.get("label", item.get("option", item.get("value", item.get("level"))))
                p = _num(item.get("probability", item.get("p")))
                key = _match_label(str(name), labels) if name is not None else (labels[i] if i < len(labels)
                                                                                 else None)
            else:
                p, key = _num(item), (labels[i] if i < len(labels) else None)
            if key is not None and p is not None:
                out[key] = p
    return out


def _match_label(k: str, labels: list[str]) -> str | None:
    if k in labels:
        return k
    head = k.split(":", 1)[0].strip()
    if head in labels:
        return head
    if k.isdigit() and int(k) < len(labels):
        return labels[int(k)]
    low = {lab.lower(): lab for lab in labels}
    return low.get(head.lower())


def _answer(qid: str, q: JevQuestion, a: Any) -> JevAnswer:
    labels = q.labels()
    conf = None
    if isinstance(a, dict):
        conf = _num(a.get("confidence"))
    if q.type == "noul":
        p = _num(a)
        if p is None and isinstance(a, dict):
            for k in ("noul", "probability", "p", "yes", "true", "value"):
                p = _num(a.get(k))
                if p is not None:
                    break
            if p is None and isinstance(a.get("probabilities"), (dict, list)):
                p = _prob_map(a["probabilities"], ["true", "false"]).get("true")
            if p is None and isinstance(a.get("noul"), bool):  # a bare verdict: take its confidence
                p = (conf if conf is not None else 1.0) if a["noul"] else 1 - (conf if conf is not None else 1.0)
        if p is None:
            raise JevError(f"{qid}: no probability in noul answer {a!r}")
        p = min(1.0, max(0.0, p))
        return JevAnswer(id=qid, type="noul", probabilities={"true": p, "false": 1 - p},
                         top="true" if p >= 0.5 else "false", confidence=conf)
    if not isinstance(a, dict):
        raise JevError(f"{qid}: unreadable {q.type} answer {a!r}")
    probs = _prob_map(a.get("probabilities", a.get("distribution", {})), labels)
    pick_raw = a.get(q.type, a.get("choice", a.get("score", a.get("label", a.get("value")))))
    pick = _match_label(str(pick_raw), labels) if pick_raw is not None else None
    if not probs and pick is None:
        raise JevError(f"{qid}: no choice or probabilities in {a!r}")
    if not probs:  # a pick with only a confidence: put the rest of the mass evenly on the others
        c = conf if conf is not None else 1.0
        rest = (1 - c) / max(1, len(labels) - 1)
        probs = {lab: (c if lab == pick else rest) for lab in labels}
    for lab in labels:
        probs.setdefault(lab, 0.0)
    top = pick or max(probs.items(), key=lambda kv: kv[1])[0]
    return JevAnswer(id=qid, type=q.type, probabilities=probs, top=top, confidence=conf)


def parse_response(body: dict, request: JevRequest) -> JevResult:
    """Normalise a Jev response body against the request that produced it."""
    if not isinstance(body, dict):
        raise JevError(f"Jev returned {type(body).__name__}, not an object")
    if body.get("error"):
        raise JevError(f"Jev error: {body['error']}")
    answers = body.get("answers", body.get("choices", body.get("results", body.get("decisions"))))
    if isinstance(answers, list):  # [{"id"|"question": ..., ...}]
        answers = {str(a.get("id", a.get("question", ""))): a for a in answers if isinstance(a, dict)}
    if not isinstance(answers, dict):
        answers = {k: v for k, v in body.items() if k in request.questions}
    out: dict[str, JevAnswer] = {}
    for qid, q in request.questions.items():
        if qid not in answers:
            raise JevError(f"Jev returned no answer for {qid}")
        out[qid] = _answer(qid, q, answers[qid])
    return JevResult(answers=out, model=str(body.get("model", "")), usage=body.get("usage") or {}, raw=body)


# --------------------------------------------------------------------------- the client

@runtime_checkable
class DecisionModel(Protocol):
    name: str
    model: str

    def decide(self, request: JevRequest) -> JevResult: ...


class JevClient:
    name = "jev"

    def __init__(self, api_key: str, model: str, base_url: str = "https://openrouter.ai/api/v1",
                 http: httpx.Client | None = None, timeout: float = 30):
        if not api_key:
            raise JevError("no Jev key: set JEV_API_KEY or OPENROUTER_API_KEY")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=timeout)
        self._headers = {"Authorization": f"Bearer {api_key}", "X-Title": "Ripple",
                         "Content-Type": "application/json"}

    @property
    def url(self) -> str:
        return f"{self.base_url}/systemone"

    def decide(self, request: JevRequest) -> JevResult:
        bad = request.problems()
        if bad:
            raise JevError("refusing to send an invalid Jev request: " + "; ".join(bad))
        payload = request.body(self.model)
        t0 = time.perf_counter()
        try:
            r = self._http.post(self.url, headers=self._headers, json=payload)
        except httpx.HTTPError as e:
            raise JevError(f"Jev transport error: {e}") from None
        ms = round((time.perf_counter() - t0) * 1000, 1)
        try:
            body = r.json()
        except ValueError:
            body = {"text": r.text[:2000]}
        log_call("jev", payload, body, ms)
        if r.status_code >= 400:
            msg = body.get("error", body) if isinstance(body, dict) else body
            raise JevError(f"Jev HTTP {r.status_code}: {str(msg)[:500]}")
        result = parse_response(body, request)
        result.ms = ms
        return result


_OVERRIDE: Any = None
_LOCK = threading.Lock()


def set_jev_client(client: Any) -> None:
    """Install a Jev client for the whole process (tests install the real client over a mock transport)."""
    global _OVERRIDE
    with _LOCK:
        _OVERRIDE = client


def get_jev_client(settings=None) -> DecisionModel:
    if _OVERRIDE is not None:
        return _OVERRIDE
    s = settings or get_settings()
    return JevClient(s.jev_key or "", s.jev_model, s.jev_base_url, timeout=s.jev_timeout)
