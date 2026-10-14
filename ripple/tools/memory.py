"""Memory tools over the tenant's `mem_<id>` graph.

* Episodic: Episode per closed incident; recall_similar_episodes scores
  0.5*[same disruption type] + 0.3*Jaccard(entities and countries) + 0.2*(1 - vector distance of summaries).
* Procedural: Playbook {steps, uses, successes, success_rate}; (:Episode)-[:USED]->(:Playbook).
* Semantic: temporal Fact {valid_at, invalid_at}; a contradiction closes the old window and SUPERSEDES it.
* Conversation: (:User)-[:HAD]->(:Conversation)-[:HAS_MSG]->(:ConvMessage).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from ripple.db import TenantScope, now_ms
from ripple.embed import get_embedder
from ripple.ingest.docs import parse_markdown
from ripple.ingest.load_synth import read_csv
from ripple.ingest.synth import SYNTH_DIR
from ripple.tools.base import ToolError, ToolResult, dedupe, logged_tool, stable_id
from ripple.tools.impact import get_incident, revenue_at_risk

PLAYBOOKS = [
    ("port-closure", "port_closure", "Reroute around the closed port", ["REROUTE_ORDERS", "NOTIFY_OWNER"], 6, 5,
     "Move open orders to lanes from the nearest open port; notify supplier owners and Customer Ops."),
    ("port-closure-expedite", "port_closure", "Expedite and wait", ["EXPEDITE", "NOTIFY_OWNER"], 2, 1,
     "Keep the lane, expedite the most valuable orders once the port reopens."),
    ("supplier-failure", "supplier_failure", "Activate qualified alternates",
     ["ACTIVATE_ALT_SUPPLIER", "PLACE_HOLD", "NOTIFY_OWNER"], 4, 3,
     "Switch impacted parts to qualified alternates outside the region; hold orders that can't be covered."),
    ("carrier-strike", "carrier_strike", "Move volume to other carriers", ["REROUTE_ORDERS", "NOTIFY_OWNER"], 3, 3,
     "Same origin and destination, different carrier; usually adds a day."),
]
SEED_NUMBERS = {"port_closure": (1_400_000.0, 520_000.0, "partial"), "carrier_strike": (900_000.0, 40_000.0, "resolved"),
                "supplier_failure": (650_000.0, 210_000.0, "partial")}


def _p(scope: TenantScope) -> str:
    return "N-" if scope.tenant_id == "nova" else ""


def signature(dtype: str, names: list[str], countries: list[str]) -> str:
    return f"{dtype.replace('_', ' ')} affecting {', '.join(names[:3])} in {', '.join(countries[:3]) or 'n/a'}"


def _key_entities(targets: list[dict]) -> tuple[list[str], list[str], list[str]]:
    """Entity ids, names and countries that characterise an incident (lanes collapse to their carrier)."""
    lanes = [t for t in targets if t["label"] == "Lane"]
    others = [t for t in targets if t["label"] != "Lane"]
    ids = [t["id"] for t in others]
    names = [str(t["name"]).replace(" [SYNTH]", "") for t in others]
    countries = dedupe(t.get("country") for t in others)
    if lanes:
        carrier = lanes[0].get("carrier") or lanes[0]["name"]
        ids.append(f"CARRIER:{carrier}")
        names.append(carrier)
    return ids, names, countries


def _incident_targets(scope: TenantScope, inc: dict) -> list[dict]:
    targets = inc["targets"]
    if any(t["label"] == "Lane" for t in targets):
        rows = scope.ops.query("MATCH (d:Disruption {id: $did})-[:AFFECTS]->(l:Lane) RETURN l.carrier AS c LIMIT 1",
                               {"did": inc["disruption"]["id"]})
        for t in targets:
            if t["label"] == "Lane" and rows:
                t["carrier"] = rows[0]["c"]
    return targets


def seed_memory(scope: TenantScope) -> dict:
    """3+ playbooks and the past episodes described in the postmortems, so the first incident can recall."""
    P = _p(scope)
    scope.mem.run("upsert_playbook", {"rows": [{"id": f"PB-{P}{slug}", "disruption_type": t, "name": n, "steps": s,
                                                "uses": u, "successes": k, "description": d}
                                               for slug, t, n, s, u, k, d in PLAYBOOKS]})
    d = SYNTH_DIR / scope.tenant_id
    ents = {r["id"]: (r["name"], r["country"]) for f in ("ports", "suppliers") for r in read_csv(d / f"{f}.csv")}
    planted = json.loads((d / "planted.json").read_text())
    emb = get_embedder()
    n = 0
    for dtype in ("port_closure", "carrier_strike"):
        doc_id = planted["postmortems"][dtype][0]
        front, paras = parse_markdown((d / "docs" / "postmortems" / f"{doc_id}.md").read_text())
        ids = [m for m in front["mentions"] if m in ents][:2]
        names = [ents[i][0].replace(" [SYNTH]", "") for i in ids]
        countries = dedupe(ents[i][1] for i in ids)
        if dtype == "carrier_strike":
            ids.append(f"CARRIER:{planted['carrier_strike_carrier']}")
            names.append(planted["carrier_strike_carrier"])
        before, after, outcome = SEED_NUMBERS[dtype]
        sig = signature(dtype, names, countries)
        summary = (f"{sig}. {front['title']}. " + " ".join(p for p in paras if p.startswith("Summary."))[:400]
                   + f" Outcome: {outcome}.")
        steps = next(s for _, t, _, s, _, _, _ in PLAYBOOKS if t == dtype)
        ts = int(datetime.fromisoformat(str(front["updated_at"])).replace(tzinfo=timezone.utc).timestamp() * 1000)
        scope.mem.run("record_episode", {
            "id": f"EPI-{P}{doc_id.split('PM-')[-1]}", "incident_id": f"PAST-{doc_id}", "type": dtype, "entity_ids": ids,
            "countries": countries, "actions": steps, "outcome": outcome, "before": before, "after": after,
            "summary": summary, "embedding": emb.embed(sig), "ts": ts,
            "playbook_id": f"PB-{P}{dtype.replace('_', '-')}", "title": front["title"], "seeded": True,
            "recorded_at": ts})
        n += 1
    return {"playbooks": len(PLAYBOOKS), "episodes": n}


@logged_tool
def get_playbook(scope: TenantScope, disruption_type: str) -> ToolResult:
    """The best playbook for a disruption type (highest success rate, then most uses)."""
    rows = scope.mem.run("get_playbook", {"type": disruption_type})
    if not rows:
        raise ToolError(f"no playbook for {disruption_type}")
    best = rows[0]
    best["success_rate"] = round(float(best["success_rate"]), 3)
    return ToolResult({"playbook": best, "alternatives": rows[1:]}, [r["id"] for r in rows], [], ["get_playbook"],
                      summary=f"Playbook {best['id']} '{best['name']}' ({best['success_rate']:.0%} success over "
                              f"{best['uses']} uses): {' -> '.join(best['steps'])}")


@logged_tool
def recall_similar_episodes(scope: TenantScope, incident_id: str, top_k: int = 3) -> ToolResult:
    """Past episodes most similar to this incident, with the score breakdown."""
    inc = get_incident(scope, incident_id)
    if not inc:
        raise ToolError(f"unknown incident {incident_id}")
    dtype = inc["disruption"]["type"]
    ids, names, countries = _key_entities(_incident_targets(scope, inc))
    qvec = get_embedder().embed(signature(dtype, names, countries))
    eps = [e for e in scope.mem.run("episodes_all", {}) if e["incident_id"] != incident_id]
    dist = {r["id"]: float(r["distance"]) for r in
            scope.mem.run("episode_vector_search", {"qvec": qvec, "k": max(50, len(eps))})} if eps else {}
    mine = set(ids) | set(countries)
    scored = []
    for e in eps:
        theirs = set(e["entity_ids"] or []) | set(e["countries"] or [])
        jac = len(mine & theirs) / len(mine | theirs) if (mine | theirs) else 0.0
        same = 1.0 if e["disruption_type"] == dtype else 0.0
        vec = max(0.0, 1.0 - dist.get(e["id"], 1.0))
        score = 0.5 * same + 0.3 * jac + 0.2 * vec
        scored.append({**e, "score": round(score, 3),
                       "breakdown": {"same_type": same, "jaccard": round(jac, 3), "vector_similarity": round(vec, 3)}})
    scored.sort(key=lambda x: (-x["score"], -(x["ts"] or 0)))
    top = scored[:top_k]
    scope.ops.run("set_incident_playbook", {"iid": incident_id, "pid": None, "recalled": [t["id"] for t in top]})
    s = (f"Similar to {top[0]['incident_id']} ({top[0]['title']}, score {top[0]['score']:.2f}, outcome "
         f"{top[0]['outcome']})" if top else "No similar past episodes")
    return ToolResult({"incident_id": incident_id, "episodes": top, "query": {"type": dtype, "entities": ids,
                                                                             "countries": countries}},
                      [t["id"] for t in top] + [t["playbook_id"] for t in top if t.get("playbook_id")]
                      + [t["incident_id"] for t in top],
                      [(t["id"], "USED", t["playbook_id"]) for t in top if t.get("playbook_id")],
                      ["episodes_all", "episode_vector_search"], summary=s)


def _outcome(before: float, after: float) -> str:
    if before <= 0 or after <= 0.2 * before:
        return "resolved"
    return "partial" if after < 0.95 * before else "failed"


@logged_tool
def record_episode(scope: TenantScope, incident_id: str) -> ToolResult:
    """Write the Episode for an incident (idempotent) and update the playbook's uses/successes the first time."""
    inc = get_incident(scope, incident_id)
    if not inc:
        raise ToolError(f"unknown incident {incident_id}")
    i, d = inc["incident"], inc["disruption"]
    dtype = d["type"]
    ids, names, countries = _key_entities(_incident_targets(scope, inc))
    live = revenue_at_risk(scope, incident_id=incident_id).data
    before = float(i.get("revenue_at_risk_initial") or live["revenue_at_risk"])
    after = float(live["revenue_at_risk"])
    acts = scope.ops.run("incident_actions", {"iid": incident_id})
    taken = dedupe(a["type"] for a in acts if a["status"] == "executed")
    outcome = _outcome(before, after)
    pid = i.get("playbook_id")
    if not pid:
        pb = scope.mem.run("get_playbook", {"type": dtype})
        pid = pb[0]["id"] if pb else None
    sig = signature(dtype, names, countries)
    summary = (f"{sig}. {i.get('orders_at_risk_initial') or 0} open orders and ${before:,.0f} at risk; actions: "
               f"{', '.join(taken) or 'none'}; ${after:,.0f} still at risk at close; outcome {outcome}.")
    eid = stable_id("EPI", scope.tenant_id, incident_id)
    rec = now_ms()
    rows = scope.mem.run("record_episode", {
        "id": eid, "incident_id": incident_id, "type": dtype, "entity_ids": ids, "countries": countries,
        "actions": taken, "outcome": outcome, "before": round(before, 2), "after": round(after, 2), "summary": summary,
        "embedding": get_embedder().embed(sig), "ts": rec, "playbook_id": pid, "title": i.get("title") or sig,
        "seeded": False, "recorded_at": rec})
    created = bool(rows and rows[0]["created"])
    pb = None
    if created and pid:
        pb = scope.mem.run("playbook_outcome", {"id": pid, "success": 1 if outcome == "resolved" else 0})[0]
    return ToolResult({"episode_id": eid, "created": created, "outcome": outcome, "revenue_before": round(before, 2),
                       "revenue_after": round(after, 2), "actions_taken": taken, "playbook_id": pid,
                       "playbook": pb, "summary": summary},
                      [eid, incident_id] + ([pid] if pid else []), [(eid, "USED", pid)] if pid else [],
                      ["revenue_at_risk", "incident_actions", "record_episode"] + (["playbook_outcome"] if pb else []),
                      summary=f"Episode {eid}: {outcome} (${before:,.0f} -> ${after:,.0f})"
                              + (f"; {pid} now {pb['successes']}/{pb['uses']}" if pb else ""))


@logged_tool
def upsert_fact(scope: TenantScope, subject_id: str, predicate: str, object: str, source: str = "agent",  # noqa: A002
                confidence: float = 1.0) -> ToolResult:
    """Record a temporal fact. A contradicting newer fact closes the old one's window (invalid_at) and SUPERSEDES it."""
    cur = scope.mem.run("fact_current", {"s": subject_id, "p": predicate})
    if cur and cur[0]["object"] == object:
        return ToolResult({"fact_id": cur[0]["id"], "created": False, "superseded": None}, [cur[0]["id"]], [],
                          ["fact_current"], summary=f"Fact unchanged: {subject_id} {predicate} = {object}")
    ts = now_ms()
    fid = stable_id("FACT", scope.tenant_id, subject_id, predicate, object, ts)
    old = cur[0]["id"] if cur else None
    scope.mem.run("fact_create", {"id": fid, "s": subject_id, "p": predicate, "o": object, "ts": ts, "source": source,
                                  "confidence": float(confidence), "old": old})
    return ToolResult({"fact_id": fid, "created": True, "superseded": old}, [fid] + ([old] if old else []),
                      [(fid, "SUPERSEDES", old)] if old else [], ["fact_current", "fact_create"],
                      summary=f"Fact {subject_id} {predicate} = {object}" + (f" (supersedes {old})" if old else ""))


@logged_tool
def facts_about(scope: TenantScope, subject_id: str, include_history: bool = False) -> ToolResult:
    """Facts about an entity: current ones, or the full history with validity windows."""
    rows = scope.mem.run("facts_about", {"s": subject_id, "history": bool(include_history)})
    return ToolResult({"subject_id": subject_id, "facts": rows}, [r["id"] for r in rows],
                      [(r["id"], "SUPERSEDES", r["supersedes"]) for r in rows if r["supersedes"]], ["facts_about"],
                      summary=f"{len(rows)} fact(s) about {subject_id}")


def log_turn(scope: TenantScope, user_id: str, conversation_id: str, role: str, text: str,
             sources: list | None = None) -> str:
    mid = f"CMSG-{time.time_ns()}"
    scope.mem.run("log_conversation_turn", {"uid": user_id, "cid": conversation_id, "mid": mid, "role": role,
                                            "text": text, "ts": now_ms(), "sources": json.dumps(sources or [])})
    return mid


def conversations(scope: TenantScope, user_id: str) -> list[dict]:
    out = []
    for r in scope.mem.run("conversations_for_user", {"uid": user_id}):
        msgs = [{**dict(m), "sources": json.loads(m["sources_json"] or "[]")} for m in r["messages"]]
        out.append({"id": r["id"], "started_at": r["started_at"], "messages": msgs})
    return out


@logged_tool
def close_incident(scope: TenantScope, incident_id: str) -> ToolResult:
    """Close: record the episode, update playbook stats and facts, feed risk back into the ops graph, SAVE."""
    inc = get_incident(scope, incident_id)
    if not inc:
        raise ToolError(f"unknown incident {incident_id}")
    ep = record_episode(scope, incident_id=incident_id).data
    dtype = inc["disruption"]["type"]
    targets = _incident_targets(scope, inc)
    facts = []
    date = time.strftime("%Y-%m-%d")
    for t in targets[:5]:
        if t["label"] == "Lane":
            continue
        pred = "reliability" if t["label"] == "Supplier" else "status"
        obj = f"{dtype.replace('_', ' ')} on {date} ({incident_id}, {ep['outcome']})"
        facts.append(upsert_fact(scope, subject_id=t["id"], predicate=pred, object=obj, source=incident_id).data)
    ids, _, _ = _key_entities(targets)
    carrier = next((i for i in ids if i.startswith("CARRIER:")), None)
    if carrier:
        facts.append(upsert_fact(scope, subject_id=carrier, predicate="reliability",
                                 object=f"strike on {date} ({incident_id}, {ep['outcome']})", source=incident_id).data)
    bump = [t["id"] for t in targets if t["label"] != "Lane"][:20]
    if bump:
        scope.ops.run("bump_risk", {"ids": bump, "delta": 0.1})
    scope.ops.run("close_incident", {"iid": incident_id, "ts": now_ms(), "outcome": ep["outcome"],
                                     "episode_id": ep["episode_id"]})
    scope.save()
    return ToolResult({"incident_id": incident_id, "episode": ep, "facts": facts, "status": "closed"},
                      [incident_id, ep["episode_id"]] + [f["fact_id"] for f in facts], [],
                      ["record_episode", "upsert_fact", "bump_risk", "close_incident"],
                      summary=f"Closed {incident_id}: {ep['outcome']}, episode {ep['episode_id']}")
