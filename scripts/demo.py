"""Terminal fallback demo: the three acts of the video (idea.md section 17), against an embedded DB.

    .venv/bin/python scripts/demo.py [--db var/demo.db] [--sample 3000] [--rebuild]

Act 1 (Track 1): Shanghai closes -> four agents trace, decide, act -> approve the reroute -> revenue at risk drops.
Act 2 (Track 2): close + record episode -> restart (DB closed and reopened) -> Ningbo congestion recalls Shanghai and
                 reuses its playbook -> tenant switch to Nova -> 20-session load test.
Act 3 (Track 3): five brain questions with sources -> owner handover posted -> the answer changes.
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from ripple.agents.events import BUS  # noqa: E402
from ripple.agents.orchestrator import Orchestrator  # noqa: E402
from ripple.db import TenantScope, close_db, get_db  # noqa: E402
from ripple.ingest.build import build_all, is_built  # noqa: E402
from ripple.ingest.delta import ingest_delta  # noqa: E402
from ripple.ingest.synth import SYNTH_DIR  # noqa: E402
from ripple.scenarios import scenario_event  # noqa: E402
from ripple.tools.actions import approve_action, execute_action, get_action, list_actions  # noqa: E402
from ripple.tools.brain import ask  # noqa: E402
from ripple.tools.memory import close_incident  # noqa: E402

W = 110


def h(title: str) -> None:
    print("\n" + "=" * W + f"\n{title}\n" + "=" * W)


def say(prefix: str, text: str) -> None:
    print(textwrap.fill(text, W, initial_indent=f"{prefix:>10} | ", subsequent_indent=" " * 13))


def timeline(iid: str) -> None:
    for e in BUS.history(iid):
        if e["kind"] == "tool_call":
            continue
        tag = f"{e['agent']}" + (f":{e['tool']}" if e["tool"] else "")
        if e["kind"] in ("handoff",):
            say("->", e["summary"])
        else:
            say(tag[:10], e["summary"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "var" / "demo.db"))
    ap.add_argument("--sample", type=int, default=3000, help="DataCo orders to load (0 = full dataset)")
    ap.add_argument("--rebuild", action="store_true")
    a = ap.parse_args()
    path = Path(a.db)
    if a.rebuild and path.exists():
        path.unlink()
    db = get_db(path, mode="embedded")
    if not is_built(db, "dataco"):
        print(f"building both tenants into {path} (sample={a.sample or 'full'}) ...")
        build_all(db, a.sample or None)
    s = TenantScope("dataco", db)

    h("ACT 1 - Agents that act on connected data: Port of Shanghai closes for 10 days")
    iid = Orchestrator(s, "scripted").run(scenario_event("port_closure_shanghai", "dataco"))
    timeline(iid)
    for act in list_actions(s, status="proposed", incident_id=iid):
        say("human", f"approves {act['type']} {act['id']}: {act['summary']}")
        approve_action(s, action_id=act["id"], user="USR-judge", user_name="Judge")
        r = execute_action(s, action_id=act["id"]).data
        say("graph", f"revenue at risk ${r['revenue_before']:,.0f} -> ${r['revenue_after']:,.0f}")
        ev = get_action(s, act["id"])["evidence"]
        say("evidence", ", ".join(f"{e['label']} {e['id']}" for e in ev[:8]) + (" ..." if len(ev) > 8 else ""))

    h("ACT 2 - Memory and coordination: close, restart, a similar incident, tenant switch")
    c = close_incident(s, incident_id=iid).data
    say("memory", f"episode {c['episode']['episode_id']} recorded, outcome {c['episode']['outcome']}; playbook "
                  f"{c['episode']['playbook_id']} now {c['episode']['playbook']['successes']}/{c['episode']['playbook']['uses']}")
    close_db(db)
    say("restart", "embedded FalkorDB stopped; reopening from the .db file")
    db = get_db(path, mode="embedded")
    s = TenantScope("dataco", db)
    iid2 = Orchestrator(s, "scripted").run(scenario_event("port_congestion_ningbo", "dataco"))
    for e in BUS.history(iid2):
        if e["agent"] in ("sentinel", "planner") and e["kind"] == "message":
            say(e["agent"], e["summary"])
    nova = TenantScope("nova", db)
    q = "Who on the team has handled a port closure before?"
    for sc in (s, nova):
        r = ask(sc, question=q).data
        say(sc.tenant_id, f"{r['answer'][:220]} [sources: {', '.join(x['doc_id'] for x in r['sources'][:3])}]")
    from load_test import run_load_test

    lt = run_load_test(db, 20)
    say("load", f"{lt['sessions']} sessions, {lt['ops']} ops in {lt['wall_s']}s: {len(lt['leaks'])} cross-tenant leaks, "
                f"{lt['duplicates']} duplicate actions")

    h("ACT 3 - Company brain: answers with sources, kept current")
    for question in ["Who owns our relationship with Shenzhen Volt Components, and who backs them up?",
                     "Why did we dual-source the Li-ion battery pack?",
                     "What does the contract with Shenzhen Volt Components say about delay penalties, and are we owed "
                     "anything for this incident?",
                     "Who on the team has handled a port closure before?",
                     "What changed in our sourcing policy since the 2024 typhoon?"]:
        r = ask(s, question=question, user_id="USR-judge").data
        say("Q", question)
        say("A", r["answer"])
        say("sources", ", ".join(x["doc_id"] for x in r["sources"][:4]))
    item = json.loads((SYNTH_DIR / "dataco" / "delta" / "handover.json").read_text())
    say("chat", item["text"])
    d = ingest_delta(s, kind="chat", text=item["text"], author_id=item["author_id"], channel=item["channel"]).data
    say("ingest", f"{d['message_id']}: {d.get('handover')}")
    r = ask(s, question="Who owns our relationship with Shenzhen Volt Components?", user_id="USR-judge").data
    say("A", r["answer"])
    say("sources", ", ".join(x["doc_id"] for x in r["sources"][:4]))
    close_db(db)


if __name__ == "__main__":
    main()
