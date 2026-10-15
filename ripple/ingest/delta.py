"""Incremental (delta) ingest while the app runs: new chat messages and documents.

A chat message becomes a ChatMessage (+ embedding, MENTIONS, POSTED) in a live thread whose Document is citable,
plus a Chunk so doc_search finds it. An owner handover ("handing over the <supplier> relationship to <person>")
closes the old OWNS_RELATIONSHIP window, opens a new one and records a Fact, so `who_owns` changes immediately.
"""

from __future__ import annotations

import hashlib
import re
import time

from ripple.db import TenantScope
from ripple.embed import get_embedder
from ripple.ingest.dataco import slug
from ripple.ingest.docs import chunk_paragraphs, parse_markdown
from ripple.tools.base import ToolError, ToolResult, logged_tool

HANDOVER = re.compile(r"hand(?:ing|ed|s)?\s*(?:it\s+)?(?:over|off)|taking over|new owner", re.I)


def _p(scope: TenantScope) -> str:
    return "N-" if scope.tenant_id == "nova" else ""


@logged_tool
def ingest_delta(scope: TenantScope, kind: str = "chat", text: str = "", author_id: str | None = None,
                 channel: str = "#general", title: str | None = None, doc_id: str | None = None) -> ToolResult:
    """Ingest one new chat message (kind=chat) or document (kind=doc, markdown with optional front matter)."""
    from ripple.tools.brain import linker
    from ripple.tools.memory import upsert_fact

    if not text.strip():
        raise ToolError("empty text")
    g = scope.ops
    emb = get_embedder()
    lk = linker(scope)
    today = time.strftime("%Y-%m-%d")
    ts = time.strftime("%Y-%m-%dT%H:%M")
    h = hashlib.sha1(f"{kind}|{channel}|{author_id}|{text}".encode()).hexdigest()[:10].upper()
    out: dict = {"kind": kind}
    nodes: list[str] = []
    edges: list[tuple] = []
    if kind == "chat":
        P = _p(scope)
        tid, did = f"THR-{P}D-{slug(channel)}", f"DOC-{P}CHAT-D-{slug(channel)}"
        g.run("delta_upsert_thread", {"tid": tid, "doc_id": did, "channel": channel, "title": f"Live: {channel}",
                                      "uri": f"live://chat/{slug(channel)}", "ts": ts})
        mid = f"MSG-{P}D-{h}"
        g.run("load_chat_messages", {"rows": [{"id": mid, "thread_id": tid, "author": author_id or "", "ts": ts,
                                               "text": text, "embedding": emb.embed(text)}]})
        cid = f"{did}#{h}"
        author = lk.names.get(author_id or "", author_id or "someone").replace(" [SYNTH]", "")
        ctext = f"{channel}: live\n\n{author} ({today}): {text}"
        g.run("load_chunks", {"rows": [{"id": cid, "doc_id": did, "text": ctext, "ordinal": 0, "embedding": emb.embed(ctext)}]})
        if author_id:
            g.run("load_authored", {"rows": [{"employee_id": author_id, "doc_id": did}]})
        found = lk.link(text)
        g.run("load_mentions", {"rows": [{"src": s, "dst": e, "confidence": c} for e, c in found.items() for s in (mid, cid)]})
        out.update(message_id=mid, thread_id=tid, doc_id=did, chunk_id=cid, mentions=sorted(found))
        nodes += [mid, tid, did, cid] + sorted(found)
        edges += [(tid, "HAS_MSG", mid), (did, "HAS_CHUNK", cid)] + [(mid, "MENTIONS", e) for e in found]
        if HANDOVER.search(text):
            sups = lk.find(text, ("Supplier",))
            emps = [(m.start(), lk.alias[m.group(1)]) for m in lk._rx.finditer(text.lower())
                    if lk.kind.get(lk.alias[m.group(1)]) == "Employee"]
            cut = max(text.lower().rfind(" to "), 0)
            after = [e for pos, e in emps if pos > cut and e != author_id]
            new_owner = after[0] if after else next((e for _, e in emps if e != author_id), None)
            if sups and new_owner:
                sid = sups[0]
                closed = g.run("handover_close", {"sid": sid, "today": today})
                g.run("handover_open", {"sid": sid, "eid": new_owner, "today": today, "source": mid})
                f = upsert_fact(scope, subject_id=sid, predicate="relationship_owner", object=new_owner, source=mid)
                out["handover"] = {"supplier_id": sid, "from": [c["employee_id"] for c in closed], "to": new_owner,
                                   "effective": today, "fact_id": f.data["fact_id"]}
                nodes += [sid, new_owner, f.data["fact_id"]]
                edges.append((new_owner, "OWNS_RELATIONSHIP", sid))
    elif kind == "doc":
        front, paras = parse_markdown(text)
        did = doc_id or front.get("id") or f"DOC-{_p(scope)}D-{h}"
        cur = g.run("doc_version", {"id": did})
        version = (cur[0]["version"] or 1) + 1 if cur else int(front.get("version", 1))
        ttl = title or front.get("title") or (paras[0].lstrip("# ") if paras else did)
        g.run("load_documents", {"rows": [{"id": did, "type": front.get("type", "sop"), "title": ttl,
                                           "uri": f"live://doc/{did}", "version": version, "updated_at": today}]})
        body = paras[1:] if paras and paras[0].startswith("#") else paras
        chunks = []
        for n, c in enumerate(chunk_paragraphs(body)):
            full = f"{ttl}\n\n{c}" if n == 0 else c
            chunks.append({"id": f"{did}#v{version}-{n}", "doc_id": did, "text": full, "ordinal": n,
                           "embedding": emb.embed(full)})
        g.run("load_chunks", {"rows": chunks})
        if author_id:
            g.run("load_authored", {"rows": [{"employee_id": author_id, "doc_id": did}]})
        rows = [{"src": c["id"], "dst": e, "confidence": conf} for c in chunks for e, conf in lk.link(c["text"]).items()]
        g.run("load_mentions", {"rows": rows})
        out.update(doc_id=did, version=version, chunks=len(chunks))
        nodes += [did] + [c["id"] for c in chunks]
    else:
        raise ToolError(f"unknown kind {kind}")
    scope.save()
    summ = f"Ingested {kind} {out.get('message_id') or out.get('doc_id')}"
    if out.get("handover"):
        summ += f"; {out['handover']['supplier_id']} now owned by {out['handover']['to']}"
    return ToolResult(out, nodes, edges, ["delta_upsert_thread", "load_chat_messages", "load_chunks", "load_mentions",
                                          "handover_close", "handover_open"], summary=summ)
