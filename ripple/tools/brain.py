"""Company-brain tools: who_owns, who_knows, trace_decision, doc_search, changes_since and the `ask` router.

Every answer carries sources ({doc_id, title, uri, chunk_id?, snippet}), the node ids it depends on (path) and the
edges between them. The router is scripted (keyword intents + dictionary entity resolution); LLM mode only
rewrites the final answer from the same tool results and is checked by the ID validator.
"""

from __future__ import annotations

import re
import threading
import time

from ripple.db import TenantScope
from ripple.embed import get_embedder, tokens
from ripple.tools.base import ToolError, ToolResult, dedupe, logged_tool

INTENTS = [
    ("owner", re.compile(r"who owns|\bowner|relationship with|backs? (?:them|him|her|us) up|point of contact|backup", re.I)),
    ("contract", re.compile(r"contract|penalt|clause|\bsla\b|\bowed\b|force majeure|liquidated", re.I)),
    ("why", re.compile(r"\bwhy\b|reason|\bdecid|decision", re.I)),
    ("expertise", re.compile(r"who knows|handled|experience|expert|who has dealt|who on the team", re.I)),
    ("change", re.compile(r"what changed|changes? (?:in|to|since)|\bsince\b|what's new|updated", re.I)),
]


def detect_intents(question: str) -> list[str]:
    found = [name for name, rx in INTENTS if rx.search(question)]
    if "expertise" in found and "owner" in found and not re.search(r"who owns|owner", question, re.I):
        found.remove("owner")
    return found or ["fallback"]


def _today() -> str:
    return time.strftime("%Y-%m-%d")


_LINKERS: dict = {}
_LINKER_LOCK = threading.Lock()


def linker(scope: TenantScope):
    """Entity linker for a tenant (cached per DB): names and ids of suppliers, parts, ports, products, employees."""
    key = (scope.tenant_id, id(scope.db))
    with _LINKER_LOCK:
        if key not in _LINKERS:
            from ripple.ingest.docs import linker_for

            _LINKERS[key] = linker_for(scope)
        return _LINKERS[key]


def _src(doc_id: str, title: str | None, uri: str | None, chunk_id: str | None = None, snippet: str = "") -> dict:
    return {"doc_id": doc_id, "title": title or doc_id, "uri": uri or "", "chunk_id": chunk_id,
            "snippet": (snippet or "")[:300]}


def _docs(scope: TenantScope, ids: list[str]) -> dict[str, dict]:
    return {r["doc_id"]: r for r in scope.ops.run("docs_get", {"ids": dedupe(ids)})} if ids else {}


def _clean(name: str | None) -> str:
    return (name or "").replace(" [SYNTH]", "")


# ------------------------------------------------------------------------------------------------ tools
@logged_tool
def doc_search(scope: TenantScope, query: str, entity_scope: list[str] | None = None, k: int = 8) -> ToolResult:
    """Vector search over document chunks, expanded through the graph to each chunk's document and the entities
    it MENTIONS. Optional entity_scope keeps only chunks that mention one of those entity ids."""
    qvec = get_embedder().embed(query)
    # the vector index is approximate (HNSW): over-fetch, then keep the k closest
    kk = max(40, int(k) * 5) * (4 if entity_scope else 1)
    rows = scope.ops.run("doc_search", {"qvec": qvec, "k": kk, "scope": list(entity_scope or [])})[: int(k)]
    sources = []
    seen = set()
    for r in rows:
        if r["doc_id"] in seen:
            continue
        seen.add(r["doc_id"])
        sources.append({**_src(r["doc_id"], r["title"], r["uri"], r["chunk_id"], r["text"]),
                        "type": r["type"], "score": round(float(r["score"]), 4)})
    nodes = [x for r in rows for x in (r["doc_id"], r["chunk_id"])] + [e for r in rows for e in r["entity_ids"]]
    edges = [(r["doc_id"], "HAS_CHUNK", r["chunk_id"]) for r in rows] + \
            [(r["chunk_id"], "MENTIONS", e) for r in rows for e in r["entity_ids"][:5]]
    return ToolResult({"query": query, "hits": rows, "sources": sources}, nodes, edges, ["doc_search"],
                      summary=f"{len(sources)} documents; top: {sources[0]['title']}" if sources else "no documents")


@logged_tool
def who_owns(scope: TenantScope, entity_id: str, at: str | None = None) -> ToolResult:
    """Current (or as-of `at`, YYYY-MM-DD) relationship owner of a supplier, with backups from the owner's team.
    For a part or port, answers for the suppliers behind it."""
    now = at or _today()
    sids = [entity_id] if entity_id.startswith("SUP-") else \
        [r["id"] for r in scope.ops.run("suppliers_for_entity", {"eid": entity_id})]
    if not sids:
        raise ToolError(f"no supplier relationship found for {entity_id}")
    owners, sources, nodes, edges = [], [], [], []
    queries = ["who_owns", "team_backups", "owner_sources", "ownership_history"]
    for sid in sids[:3]:
        rows = scope.ops.run("who_owns", {"sid": sid, "now": now})
        hist = scope.ops.run("ownership_history", {"sid": sid})
        if not rows:
            owners.append({"supplier_id": sid, "owner": None, "history": hist})
            continue
        o = rows[0]
        backups = scope.ops.run("team_backups", {"team_id": o["team_id"], "eid": o["employee_id"], "sid": sid})
        src = scope.ops.run("owner_sources", {"sid": sid, "eid": o["employee_id"]})[0]
        msgs = sorted([m for m in src["messages"] if m.get("msg")], key=lambda m: m.get("ts") or "", reverse=True)
        for m in msgs[:2]:
            if m.get("doc"):
                sources.append(_src(m["doc"], m["title"], m["uri"], m["msg"], m["text"]))
            nodes.append(m["msg"])
        if src["contract_doc"]:
            sources.append(_src(src["contract_doc"], src["contract_title"], src["contract_uri"],
                                snippet=f"Relationship owner named in {src['contract_title']}"))
        owners.append({**o, "backups": backups[:2], "history": hist})
        nodes += [sid, o["employee_id"], o["team_id"]] + [b["employee_id"] for b in backups[:2]] + \
            ([src["contract_doc"]] if src["contract_doc"] else [])
        edges += [(o["employee_id"], "OWNS_RELATIONSHIP", sid), (o["employee_id"], "MEMBER_OF", o["team_id"])] + \
                 [(b["employee_id"], "MEMBER_OF", o["team_id"]) for b in backups[:2]]
    first = next((o for o in owners if o.get("employee_id")), None)
    summary = (f"{_clean(first['name'])} ({first['employee_id']}, {first['role']}) owns {_clean(first['supplier'])} "
               f"since {first['valid_from']}") if first else f"no current owner for {entity_id}"
    return ToolResult({"entity_id": entity_id, "at": now, "owners": owners, "sources": _dedupe_sources(sources)},
                      nodes, edges, queries, summary=summary)


@logged_tool
def who_knows(scope: TenantScope, topic: str | None = None, entity_id: str | None = None, k: int = 5) -> ToolResult:
    """Employees ranked by what they authored, posted and decided about an entity or a topic (topic -> doc_search)."""
    if entity_id:
        rows = scope.ops.run("who_knows", {"ids": [entity_id], "k": int(k)})
        src_ids = dedupe(s for r in rows for s in r["sources"] if s.startswith("DOC"))
        queries = ["who_knows"]
    else:
        if not topic:
            raise ToolError("who_knows needs a topic or an entity_id")
        hits = doc_search(scope, query=topic, k=12).data["sources"]
        weight = {"postmortem": 0, "chat_thread": 1}
        docs = [h["doc_id"] for h in sorted(hits[:8], key=lambda h: weight.get(h.get("type"), 2))][:6]
        rows = scope.ops.run("who_knows_docs", {"docs": docs, "k": int(k)})
        src_ids = docs
        queries = ["doc_search", "who_knows_docs"]
    meta = _docs(scope, src_ids)
    sources = [_src(d, meta[d]["title"], meta[d]["uri"], meta[d]["chunk_id"], meta[d]["text"]) for d in src_ids if d in meta]
    nodes = [r["employee_id"] for r in rows] + src_ids + ([entity_id] if entity_id else [])
    edges = [(r["employee_id"], "AUTHORED", s) for r in rows for s in r["sources"][:3] if s.startswith("DOC")]
    lead = rows[0] if rows else None
    return ToolResult({"topic": topic, "entity_id": entity_id, "people": rows, "sources": sources[:6]}, nodes, edges,
                      queries, summary=(f"{_clean(lead['name'])} ({lead['employee_id']}, {lead['role']}) knows most "
                                        f"(score {lead['score']})") if lead else "nobody found")


def _rank_decisions(scope: TenantScope, question: str, ids: list[str]) -> list[dict]:
    qt = set(tokens(question))
    out = []
    for d in scope.ops.run("decisions_all", {}):
        dt = set(tokens(d["summary"] + " " + " ".join(n or "" for n in d["about_names"])))
        score = len(qt & dt) + (3 if set(d["about"]) & set(ids) else 0)
        if score >= 2:
            out.append({**d, "score": score})
    return sorted(out, key=lambda d: (-d["score"], d["decided_at"]), reverse=False)


@logged_tool
def trace_decision(scope: TenantScope, entity_id: str | None = None, question: str | None = None,
                   decision_id: str | None = None) -> ToolResult:
    """Why was something decided: Decision -> SOURCED_FROM documents and chat messages -> the people involved."""
    if decision_id:
        rows = scope.ops.run("trace_decision_ids", {"ids": [decision_id]})
        queries = ["trace_decision_ids"]
    else:
        ids = [entity_id] if entity_id else linker(scope).find(question or "", ("Part", "Supplier", "Port"))
        ranked = _rank_decisions(scope, question or "", ids) if question else []
        if ranked:
            top = [d["id"] for d in ranked if d["score"] >= ranked[0]["score"] - 1][:2]
            rows = scope.ops.run("trace_decision_ids", {"ids": top})
            queries = ["decisions_all", "trace_decision_ids"]
        elif ids:
            rows = scope.ops.run("trace_decision", {"ids": ids})
            queries = ["trace_decision"]
        else:
            raise ToolError("trace_decision needs an entity, a decision id or a question that matches a decision")
    decisions: dict[str, dict] = {}
    doc_ids = []
    for r in rows:
        d = decisions.setdefault(r["decision_id"], {"decision_id": r["decision_id"], "summary": r["summary"],
                                                    "decided_at": r["decided_at"], "sources": [], "people": set()})
        d["sources"].append({"type": r["source_type"], "id": r["source_id"], "text": (r["source_text"] or "")[:300],
                             "thread_doc": r["thread_doc"], "authors": r["authors"]})
        d["people"] |= set(r["people"]) | set(r["authors"])
        doc_ids.append(r["source_id"] if r["source_type"] == "Document" else r["thread_doc"])
    for d in decisions.values():
        d["people"] = sorted(_clean(p) for p in d["people"])
    doc_ids = [x for x in dedupe(doc_ids) if x]
    doc_ids.sort(key=lambda x: 0 if "-PM-" in x else (2 if "CHAT" in x else 1))
    meta = _docs(scope, doc_ids)
    sources = [_src(x, meta[x]["title"], meta[x]["uri"], meta[x]["chunk_id"], meta[x]["text"]) for x in doc_ids if x in meta]
    nodes = list(decisions) + [s["id"] for d in decisions.values() for s in d["sources"]] + doc_ids
    edges = [(d["decision_id"], "SOURCED_FROM", s["id"]) for d in decisions.values() for s in d["sources"]]
    lst = list(decisions.values())
    return ToolResult({"decisions": lst, "sources": sources}, nodes, edges, queries,
                      summary=(f"{lst[0]['decision_id']} ({lst[0]['decided_at']}): {lst[0]['summary']}" if lst
                               else "no decision found"))


@logged_tool
def changes_since(scope: TenantScope, question: str, since: str | None = None) -> ToolResult:
    """What changed: revised documents (version > 1) and decisions since a date (default: a year in the question)."""
    if not since:
        m = re.search(r"(20\d\d)", question)
        since = f"{m.group(1)}-01-01" if m else "2000-01-01"
    docs = scope.ops.run("docs_changed_since", {"since": since})
    qt = set(tokens(question))
    decs = [d for d in scope.ops.run("decisions_all", {}) if (d["decided_at"] or "") >= since]
    for d in decs:
        d["score"] = len(qt & set(tokens(d["summary"])))
    decs = sorted([d for d in decs if d["score"] > 0], key=lambda d: (-d["score"], d["decided_at"]))[:4]
    docs = sorted(docs, key=lambda d: -len(qt & set(tokens(d["title"] + " " + " ".join(d["texts"])))))
    sources = [_src(d["doc_id"], d["title"], d["uri"], (d["chunk_ids"] or [None])[0], " ".join(d["texts"])[:300])
               for d in docs[:3]]
    if decs:
        tr = scope.ops.run("trace_decision_ids", {"ids": [d["id"] for d in decs]})
        extra = [r["source_id"] if r["source_type"] == "Document" else r["thread_doc"] for r in tr]
        meta = _docs(scope, [x for x in extra if x])
        sources += [_src(x, meta[x]["title"], meta[x]["uri"], meta[x]["chunk_id"], meta[x]["text"])
                    for x in dedupe(extra) if x in meta]
    nodes = [d["doc_id"] for d in docs[:3]] + [d["id"] for d in decs]
    return ToolResult({"since": since, "documents": docs[:3], "decisions": decs, "sources": _dedupe_sources(sources)[:6]},
                      nodes, [], ["docs_changed_since", "decisions_all", "trace_decision_ids"],
                      summary=f"{len(docs)} revised documents and {len(decs)} relevant decisions since {since}")


def _dedupe_sources(sources: list[dict]) -> list[dict]:
    seen, out = set(), []
    for s in sources:
        if s["doc_id"] not in seen:
            seen.add(s["doc_id"])
            out.append(s)
    return out


# ------------------------------------------------------------------------------------------------ router
def _incident_suppliers(scope: TenantScope, incident_id: str | None) -> list[str]:
    if not incident_id:
        return []
    rows = scope.ops.run("related_suppliers", {"iid": incident_id, "limit": 3})
    return [r["id"] for r in rows if r["contract_id"]] or [r["id"] for r in rows]


@logged_tool
def ask(scope: TenantScope, question: str, user_id: str | None = None, conversation_id: str | None = None,
        incident_id: str | None = None, mode: str = "scripted") -> ToolResult:
    """Answer a company question (who owns / why did we / contract / who knows / what changed / anything) with
    sources and the graph path behind the answer."""
    from ripple.tools.sourcing import contract_terms

    intents = detect_intents(question)
    lk = linker(scope)
    ents = lk.find(question)
    sups = [e for e in ents if lk.kind.get(e) == "Supplier"]
    others = [e for e in ents if lk.kind.get(e) in ("Part", "Port")]
    target_sups = sups or _incident_suppliers(scope, incident_id)
    parts: list[str] = []
    results: list[ToolResult] = []
    for intent in intents:
        try:
            if intent == "owner":
                eid = (target_sups or others or [None])[0]
                if not eid:
                    raise ToolError("which supplier?")
                r = who_owns(scope, entity_id=eid)
                for o in r.data["owners"]:
                    if not o.get("employee_id"):
                        continue
                    b = ", ".join(f"{_clean(x['name'])} ({x['employee_id']})" for x in o.get("backups", []))
                    parts.append(f"{_clean(o['name'])} ({o['employee_id']}, {o['role']}, {o['team']}) owns the "
                                 f"relationship with {_clean(o['supplier'])} ({o['supplier_id']}) since {o['valid_from']}."
                                 + (f" Backup: {b}." if b else ""))
            elif intent == "contract":
                sid = (target_sups or [None])[0]
                if not sid:
                    raise ToolError("which supplier's contract?")
                clause = "force majeure" if re.search(r"force majeure", question, re.I) else \
                    ("lead time SLA" if re.search(r"\bsla\b|lead time", question, re.I) else "delay penalty")
                r = contract_terms(scope, supplier_id=sid, clause=clause, incident_id=incident_id)
                d = r.data
                txt = (f"Contract {d['contract_id']} with {_clean(d['supplier'])}: {d['clause_text']}")
                if d.get("penalty"):
                    p = d["penalty"]
                    txt += (f" For {incident_id}: {p['exposed_orders']} exposed orders worth ${p['exposed_revenue']:,.0f}, "
                            f"{p['delay_days']} days of delay -> " + ("force majeure applies, so nothing is owed."
                                                                      if p["force_majeure_applies"] else
                                                                      f"we are owed ${p['owed']:,.0f} (capped)."))
                elif re.search(r"owed|incident", question, re.I) and not incident_id:
                    txt += " (Open an incident to compute what is owed.)"
                d["sources"] = [_src(d["doc_id"], d["title"], d["uri"], (d["chunks"][0]["chunk_id"] if d["chunks"] else None),
                                     d["clause_text"])]
                parts.append(txt)
            elif intent == "why":
                r = trace_decision(scope, question=question)
                for dd in r.data["decisions"][:2]:
                    srcs = ", ".join(dedupe(s["thread_doc"] or s["id"] for s in dd["sources"]))
                    parts.append(f"{dd['decision_id']} ({dd['decided_at']}): {dd['summary']}. Sources: {srcs}. "
                                 f"People: {', '.join(dd['people'][:4])}.")
            elif intent == "expertise":
                eid = (others or sups or [None])[0] if re.search(r"\b(supplier|part|port)\b", question, re.I) else None
                r = who_knows(scope, topic=None if eid else question, entity_id=eid)
                ppl = r.data["people"][:3]
                parts.append("Most experienced: " + "; ".join(
                    f"{_clean(p['name'])} ({p['employee_id']}, {p['role']}, {p['team']})" for p in ppl)
                    + (f", based on {', '.join(s['doc_id'] for s in r.data['sources'][:3])}." if r.data["sources"] else "."))
            elif intent == "change":
                r = changes_since(scope, question=question)
                ds = "; ".join(f"{d['title']} v{d['version']} ({d['updated_at']}, {d['doc_id']})" for d in r.data["documents"][:2])
                dc = "; ".join(f"{d['id']} ({d['decided_at']}): {d['summary']}" for d in r.data["decisions"][:3])
                parts.append(f"Since {r.data['since'][:4]}: " + (f"revised {ds}. " if ds else "") + (f"Decisions: {dc}." if dc else ""))
            else:
                r = doc_search(scope, query=question, entity_scope=ents or None, k=6)
                if not r.data["sources"] and ents:
                    r = doc_search(scope, query=question, k=6)
                top = r.data["sources"][:3]
                parts.append("Relevant: " + " | ".join(f"{s['title']} ({s['doc_id']}): {s['snippet'][:160]}" for s in top))
            r.data["intent"] = intent
            results.append(r)
        except ToolError as e:
            parts.append(f"({intent}: {e})")
    sources = _dedupe_sources([s for r in results for s in r.data.get("sources", [])])[:8]
    path = dedupe([n for r in results for n in r.node_ids] + ents)
    edges = dedupe([e for r in results for e in r.edges])
    answer = " ".join(parts) or "I could not find that in the graph."
    used_mode = "scripted"
    if mode == "llm":
        from ripple.agents.llm import compose_answer

        better = compose_answer(question, answer, [r.to_dict() for r in results], set(path) | {s["doc_id"] for s in sources})
        if better:
            answer, used_mode = better, "llm"
    data = {"answer": answer, "sources": sources, "path": path, "edges": [list(e) for e in edges], "intent": intents,
            "entities": ents, "mode": used_mode}
    if user_id:
        from ripple.tools.memory import log_turn

        cid = conversation_id or f"CONV-{user_id}-{time.strftime('%Y%m%d')}"
        log_turn(scope, user_id, cid, "user", question)
        log_turn(scope, user_id, cid, "assistant", answer, sources)
        data["conversation_id"] = cid
    return ToolResult(data, path, edges, dedupe(q for r in results for q in r.queries), summary=answer[:200])
