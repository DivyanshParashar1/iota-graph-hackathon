"""Terminal walk-through of the three demo acts, against a real LLM and a real FalkorDB.

    .venv/bin/python scripts/demo.py --company "Northwind Trainers" --industry footwear

It plays the user's half of the interview with a second LLM (the persona in `tests/test_llm_live.py`), so the
whole thing runs unattended: interview -> forms -> ontology -> approve and load -> experts -> ask one a
question. Everything it does goes through the same code the UI drives, and everything it writes stays in the
`.db` file it was given, so you can point the API at it afterwards and click through the result.

    --db var/demo.db        where to put the graph (default: a temporary directory)
    --turns 20              cap on interview turns
    --stop-after ontology   stop early (interview | data | ontology | experts)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ripple.config import get_settings  # noqa: E402
from ripple.db import TenantScope, close_db, get_db, slug_tenant_id  # noqa: E402
from ripple.experts import runtime  # noqa: E402
from ripple.llm.base import LLMError, get_client  # noqa: E402
from ripple.llm.structured import ask_model  # noqa: E402
from ripple.onboarding import session as sess  # noqa: E402
from ripple.onboarding import store  # noqa: E402
from ripple.onboarding.agents import ontologist  # noqa: E402
from ripple.onboarding.agents.common import state_message  # noqa: E402
from ripple.onboarding.agents.data_agent import save_values  # noqa: E402
from ripple.onboarding.events import BUS  # noqa: E402
from ripple.onboarding.models import SynthesizedForm  # noqa: E402

C = {"dim": "\033[2m", "b": "\033[1m", "cyan": "\033[36m", "green": "\033[32m", "yellow": "\033[33m",
     "red": "\033[31m", "violet": "\033[35m", "off": "\033[0m"}


def say(tag: str, text: str, colour: str = "off") -> None:
    print(f"{C[colour]}{tag:>12}{C['off']} {text}")


def rule(title: str) -> None:
    print(f"\n{C['b']}{'─' * 4} {title} {'─' * max(4, 72 - len(title))}{C['off']}")


def drain(tenant: str, after: int) -> int:
    """Print the agent steps that happened since `after` - the terminal's version of the live trail."""
    for ev in BUS.history(tenant, after):
        after = ev["seq"]
        say(ev["agent"], f"{C['dim']}{ev['kind']}: {ev['summary']}{C['off']}")
    return after


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--company", default="Northwind Trainers")
    ap.add_argument("--industry", default="footwear")
    ap.add_argument("--db", default="")
    ap.add_argument("--turns", type=int, default=24)
    ap.add_argument("--stop-after", choices=["interview", "data", "ontology", "experts"], default="experts")
    ap.add_argument("--question", default="")
    a = ap.parse_args()

    s = get_settings()
    if not s.has_llm:
        print(f"{C['red']}No LLM provider.{C['off']} Install the `claude` CLI and log in, or set "
              "OPENROUTER_API_KEY / ANTHROPIC_API_KEY. See .env.example.")
        raise SystemExit(2)
    from tests.test_llm_live import PERSONA  # the demo's user is the live suite's persona

    client = get_client()
    db_path = Path(a.db) if a.db else Path(__import__("tempfile").mkdtemp()) / "demo.db"
    db = get_db(db_path, mode="embedded")
    seen = 0
    t0 = time.time()
    try:
        rule(f"Act 1 · an empty database, then an interview ({s.llm_provider} · {s.model_name})")
        say("ripple", f"graphs before: {db.list_graphs() or 'none'}", "dim")
        tid = slug_tenant_id(a.company)
        scope = sess.start(db, a.company, a.industry, tenant_id=tid)
        sid = store.get_session(scope)["id"]
        say("ripple", f"tenant {C['b']}{scope.tenant_id}{C['off']} · graphs: {db.list_graphs()}", "green")
        seen = drain(scope.tenant_id, seen)

        for _turn in range(a.turns):
            state = sess.state(scope)
            if state["stage"] != "interview" and a.stop_after == "interview":
                break
            if state["stage"] in ("ontology", "experts", "ready"):
                break
            agent_msgs = [m for m in state["messages"] if m["role"] == "agent"]
            text = agent_msgs[-1]["text"] if agent_msgs else ""
            if state["open_form"]:
                form = store.open_form(scope)
                rule(f"Act 1 · form round {form.round}: {form.title}")
                for f in form.fields:
                    kind = f"{f.type}{f' in {f.unit}' if f.unit else ''}"
                    say("form", f"{f.label} {C['dim']}({kind}){C['off']}")
                values = fill_form(client, PERSONA, form)
                save_values(scope, form, values, confidences=dict.fromkeys(values, "ballpark"))
                store.set_form_status(scope, form.id, "submitted")
                say("user", f"filled {len(values)} of {len(form.fields)} fields", "cyan")
                sess.run_turn(scope, sid, None)
                seen = drain(scope.tenant_id, seen)
                continue
            say(state["stage"], text.replace("\n", "\n             "))
            reply = client.complete(system=PERSONA, messages=[{"role": "user", "content": text}],
                                    max_tokens=800, effort="low").text.strip()
            say("user", reply.replace("\n", " ")[:400], "cyan")
            sess.run_turn(scope, sid, reply)
            seen = drain(scope.tenant_id, seen)

        brief, row = store.current_brief(scope)
        rule("Act 1 · the brief")
        if brief:
            say("brief", f"v{row['version']} · {len(brief.products)} products, {len(brief.suppliers)} suppliers, "
                         f"{len(brief.sites)} sites, gaps: {brief.core_gaps() or 'none'}", "green")
            for p in brief.pains[:3]:
                say("pain", p, "yellow")
        if a.stop_after == "interview":
            return summary(scope, t0, db_path)

        rule("Act 2 · the ontology")
        spec, srow = store.current_spec(scope)
        if spec is None:
            say("ripple", "no spec yet (the data stage is still open)", "red")
            return summary(scope, t0, db_path)
        say("spec", f"v{srow['version']} · {len(spec.types)} types, {len(spec.relationships)} relationships",
            "violet")
        for t in spec.types:
            say(t.label, f"{C['dim']}{', '.join(p.name for p in t.properties)}{C['off']}")
        for r in spec.relationships:
            say("edge", f"({r.from_})-[{r.type}]->({r.to})", "violet")
        if a.stop_after == "ontology":
            return summary(scope, t0, db_path)

        rule("Act 2 · approve: indexes, instance data, provenance")
        from ripple.onboarding.events import StepEmitter

        out = ontologist.approve(scope, sid, StepEmitter(scope, "ontology", "ontologist"), client=client)
        seen = drain(scope.tenant_id, seen)
        say("loaded", f"{out['nodes']} nodes, {out['edges']} edges, {out['provenance']} provenance links", "green")
        counts = store.instance_counts(scope)
        say("counts", json.dumps(counts["nodes"]), "dim")
        node_id = next(iter(scope.ops.query(
            "MATCH (n) WHERE NOT any(l IN labels(n) WHERE l STARTS WITH '_') RETURN n.id AS id LIMIT 1")), {})
        if node_id.get("id"):
            prov = store.provenance_of(scope, node_id["id"])
            say("provenance", f"{node_id['id']} <- " + ", ".join(
                f"{p['source_label']}:{p['source_ref']}={str(p['source_value'])[:40]}" for p in prov) or "none",
                "green")
        sess.advance(scope, sid, "ontology", reason="approved by scripts/demo.py")
        seen = drain(scope.tenant_id, seen)

        rule("Act 3 · the experts this supply chain needs")
        roles = store.list_experts(scope)
        for r in roles:
            say(r.name, f"{r.title} · {', '.join(r.focus_types)}", "green")
            say("", f"{C['dim']}{r.justification[:160]}{C['off']}")
        if not roles:
            return summary(scope, t0, db_path)

        rule("Act 3 · ask one of them, over the real graph")
        role = roles[0]
        store.set_expert_status(scope, role.id, "approved")
        question = a.question or (role.playbook[0] if role.playbook else f"What do you cover for {a.company}?")
        say("question", question, "cyan")
        res = runtime.ask(scope, role, question, client=client,
                          on_step=lambda ev: say(role.name, f"{C['dim']}{ev['kind']}: "
                                                            f"{ev.get('tool') or ev.get('summary', '')}{C['off']}"))
        say(role.name, (res["text"] or res["reason"]).replace("\n", "\n             "),
            "green" if res["ok"] else "red")
        say("ids", ", ".join(res["ids"][:12]) or "none", "dim")
        summary(scope, t0, db_path)
    except LLMError as e:
        say("error", str(e), "red")
        raise SystemExit(1) from None
    finally:
        db.save()
        close_db(db)


def fill_form(client, persona: str, form) -> dict:
    out, _ = ask_model(client, SynthesizedForm, persona + (
        "\n\nFill in this form about your own company. Return one value per field id, using the real numbers "
        "from your brief where they apply and leaving out anything you would not know."),
        [state_message("Form", {"form": {"title": form.title, "intro": form.intro,
                                          "fields": [x.model_dump() for x in form.fields]}})])
    fields = form.field_map()
    return {k: v for k, v in (out.values or {}).items() if k in fields}


def summary(scope: TenantScope, t0: float, db_path: Path) -> None:
    rule("summary")
    c = store.counts(scope)
    steps = store.list_steps(scope, limit=5000)
    say("graph", f"{c['nodes']} nodes, {c['edges']} edges in {scope.ops.name}", "green")
    say("agents", f"{len(steps)} recorded steps, {len([s for s in steps if s['kind'] == 'llm'])} LLM calls",
        "green")
    say("time", f"{time.time() - t0:.0f}s", "dim")
    say("db", str(db_path), "dim")
    print(f"\n{C['dim']}Point the API at it:  RIPPLE_DB_PATH={db_path} .venv/bin/uvicorn "
          f"ripple.api.app:app{C['off']}")


if __name__ == "__main__":
    main()
