"""The workspace chat: one conversation with an orchestrator that deploys the expert agents as tools.

The orchestrator is an LLM with two tools: `consult_experts` (a batch of questions, one per expert, run in
parallel through the M5 expert runtime) and `describe_ontology`. It chooses which experts to consult and when it
has enough. That is a deliberate exception to the M8 rule that only Jev decides: the owner chose LLM routing for
this conversational feature. The incident pipeline is unchanged and still routes through Jev.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ripple.db import TenantScope
from ripple.experts import runtime
from ripple.llm.base import LLMClient, get_client
from ripple.llm.loop import run_tool_loop
from ripple.onboarding.events import StepEmitter
from ripple.onboarding.models import ExpertRole
from ripple.onboarding.store import list_experts
from ripple.tools.base import call_context
from ripple.tools.registry import call_tool, specs
from ripple.workspace.store import Employee

AGENT = "orchestrator"
STAGE = "workspace"
PARALLEL = 4
MAX_ASKS = 6
HISTORY = 10
PROMPT = Path(__file__).parent / "prompts" / "orchestrator.md"


def consult_spec(roles: list[ExpertRole]) -> dict:
    return {
        "name": "consult_experts",
        "description": "Ask one or more expert agents a question each. They run in parallel against the "
                       "knowledge graph and each returns its answer and the object ids it used.",
        "input_schema": {"type": "object", "required": ["asks"], "additionalProperties": False, "properties": {
            "asks": {"type": "array", "minItems": 1, "maxItems": MAX_ASKS, "items": {
                "type": "object", "required": ["expert", "question"], "additionalProperties": False,
                "properties": {"expert": {"type": "string", "enum": [r.name for r in roles]},
                               "question": {"type": "string"}}}}}},
    }


def system_prompt(employee: Employee, roles: list[ExpertRole]) -> str:
    mine = [r for r in roles if r.id in employee.role_ids]
    roster = "\n".join(
        f"- `{r.name}` - {r.title}: {r.mandate} (reasons over {', '.join(r.focus_types) or 'the graph'})"
        for r in roles)
    me = employee.name + (f", {employee.title}" if employee.title else "")
    works_as = ", ".join(r.title for r in mine) or "no expert role assigned"
    return (f"{PROMPT.read_text(encoding='utf-8').strip()}\n\n## The employee\n\n{me}. Works as: {works_as}.\n\n"
            f"## The experts you can deploy\n\n{roster}\n")


def task(history: list[dict], text: str) -> str:
    lines = [f"{'Employee' if m['role'] == 'user' else 'You'}: {m['text']}"
             for m in history[-HISTORY:] if m.get("text")]
    prior = ("## The conversation so far\n\n" + "\n\n".join(lines) + "\n\n") if lines else ""
    return f"{prior}## The employee's new message\n\n{text}"


def run(scope: TenantScope, employee: Employee, thread_id: str, history: list[dict], text: str,
        client: LLMClient | None = None) -> dict:
    """Answer one employee message. Returns {ok, text, reason, delegations, ids, turns}."""
    client = client or get_client()
    roles = [r for r in list_experts(scope) if r.status == "approved"]
    if not roles:
        raise ValueError("there are no approved expert roles to deploy yet")
    by_name = {r.name: r for r in roles}
    emit = StepEmitter(scope, STAGE, AGENT)
    delegations: list[dict] = []

    def one(a: dict) -> dict:
        role = by_name[a["expert"]]
        ex = StepEmitter(scope, STAGE, role.name)
        out = runtime.ask(scope, role, a["question"], client=client,
                          on_step=lambda ev, e=ex: e(ev["kind"], ev.get("summary") or ev.get("tool") or "",
                                                      data={"thread": thread_id}))
        return {"expert": role.name, "title": role.title, "question": a["question"], "ok": bool(out.get("ok")),
                "answer": out.get("text") or out.get("reason") or "", "ids": list(out.get("ids") or []),
                "tool_calls": sum(1 for s in out.get("steps") or [] if s.get("kind") == "tool_call")}

    def consult(asks: list[dict]) -> dict:
        asks = [a for a in asks if a.get("expert") in by_name and (a.get("question") or "").strip()][:MAX_ASKS]
        if not asks:
            raise ValueError(f"name at least one expert from: {sorted(by_name)}")
        emit("llm", f"deploying {len(asks)} expert agent(s)",
             data={"thread": thread_id, "asks": [{"expert": a["expert"], "question": a["question"]} for a in asks]})
        with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
            results = list(pool.map(one, asks))
        delegations.extend(results)
        return {"summary": f"{len(results)} expert answer(s)",
                "node_ids": sorted({i for r in results for i in r["ids"]}),
                "data": [{k: r[k] for k in ("expert", "title", "question", "ok", "answer", "ids")} for r in results]}

    def call(name: str, args: dict):
        if name == "consult_experts":
            return consult(list(args.get("asks") or []))
        with call_context(agent=AGENT):
            res = call_tool(scope, name, args)
        return {"summary": res.summary, "node_ids": res.node_ids, "data": res.data}

    def on_step(ev: dict) -> None:
        if ev["kind"] in ("answer", "error"):
            emit(ev["kind"], ev.get("summary") or "", data={"thread": thread_id})

    emit("llm", "orchestrator: reading the question", data={"thread": thread_id})
    out = run_tool_loop(client, system=system_prompt(employee, roles), task=task(history, text),
                        tools=[consult_spec(roles), *specs(["describe_ontology"])], call=call, on_step=on_step,
                        max_turns=6)
    return {"ok": bool(out.get("ok")), "text": out.get("text") or "", "reason": out.get("reason") or "",
            "delegations": delegations, "ids": list(out.get("ids") or []), "turns": out.get("turns") or 0}
