"""Company-brain ingest: contracts/SOPs/postmortems (markdown + front matter) and chat threads (JSON)
-> Document, Chunk, Thread, ChatMessage, MENTIONS, Decision, AUTHORED, SOURCED_FROM, ABOUT, PARTICIPATED_IN.

Entity linking: exact, case-insensitive match of entity ids and names ("[SYNTH]" optional) from an in-memory
dictionary -> MENTIONS {confidence: 1.0}; front-matter mentions -> confidence 1.0; fuzzy token overlap >= 0.8
on multi-word supplier names -> 0.7.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import yaml

from ripple import ROOT
from ripple.db import TenantScope
from ripple.embed import get_embedder, tokens
from ripple.ingest.load_synth import read_csv
from ripple.ingest.synth import SYNTH_DIR

MIN_WORDS, MAX_WORDS = 120, 200


def parse_markdown(text: str) -> tuple[dict, list[str]]:
    front: dict = {}
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        front = yaml.safe_load(fm)
    else:
        body = text
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    return front, paras


def chunk_paragraphs(paras: list[str]) -> list[str]:
    """~120-200 word chunks of whole paragraphs, with one paragraph of overlap between chunks."""
    chunks: list[str] = []
    i = 0
    while i < len(paras):
        cur = [paras[i]]
        words = len(paras[i].split())
        j = i + 1
        while j < len(paras) and words < MIN_WORDS and words + len(paras[j].split()) <= MAX_WORDS:
            cur.append(paras[j])
            words += len(paras[j].split())
            j += 1
        chunks.append("\n\n".join(cur))
        if j >= len(paras):
            break
        i = j - 1 if j - 1 > i else j  # overlap: next chunk starts with this chunk's last paragraph
    return chunks


class EntityLinker:
    """Dictionary entity linker over suppliers, parts, ports, products and employees."""

    def __init__(self, tenant: str, extra: dict[str, str] | None = None):
        d = SYNTH_DIR / tenant
        self.alias: dict[str, str] = {}
        self.names: dict[str, str] = {}
        self.kind: dict[str, str] = {}

        def add(eid: str, name: str, kind: str):
            self.names[eid] = name
            self.kind[eid] = kind
            base = name.replace(" [SYNTH]", "").strip()
            for a in {base.lower(), name.lower(), eid.lower()}:
                if len(a) >= 4:
                    self.alias.setdefault(a, eid)

        for s in read_csv(d / "suppliers.csv"):
            add(s["id"], s["name"], "Supplier")
        for p in read_csv(d / "parts.csv"):
            add(p["id"], p["name"], "Part")
        for p in read_csv(d / "ports.csv"):
            add(p["id"], p["name"], "Port")
            first = re.split(r"[-(/]", p["name"])[0].strip().lower()
            if len(first) >= 4:
                self.alias.setdefault(first, p["id"])
            m = re.search(r"\(([^)]+)\)", p["name"])
            if m:
                self.alias.setdefault(m.group(1).lower(), p["id"])
        for e in read_csv(d / "employees.csv"):
            add(e["id"], e["name"], "Employee")
        prods = d / "products.csv"
        if prods.exists():
            for p in read_csv(prods):
                add(p["id"], p["name"], "Product")
        for eid, name in (extra or {}).items():
            add(eid, name, "Product")
        keys = sorted(self.alias, key=len, reverse=True)
        self._rx = re.compile(r"(?<![\w-])(" + "|".join(re.escape(k) for k in keys) + r")(?![\w-])")
        self._fuzzy = [(eid, set(tokens(n.replace(" [SYNTH]", "")))) for eid, n in self.names.items()
                       if self.kind[eid] == "Supplier"]

    def link(self, text: str) -> dict[str, float]:
        low = text.lower()
        found = {self.alias[m.group(1)]: 1.0 for m in self._rx.finditer(low)}
        toks = set(tokens(text))
        for eid, ts in self._fuzzy:
            if eid not in found and len(ts) >= 2 and len(ts & toks) / len(ts) >= 0.8:
                found[eid] = 0.7
        return found

    def find(self, text: str, kinds: tuple[str, ...] | None = None) -> list[str]:
        """Entity ids mentioned in text, in order of appearance (used by the brain router)."""
        out: list[str] = []
        for m in self._rx.finditer(text.lower()):
            eid = self.alias[m.group(1)]
            if eid not in out and (kinds is None or self.kind[eid] in kinds):
                out.append(eid)
        return out


def _product_names(scope: TenantScope) -> dict[str, str]:
    return {r["id"]: r["name"] for r in scope.ops.query("MATCH (p:Product) RETURN p.id AS id, p.name AS name")}


def ingest_docs(scope: TenantScope) -> dict:
    t0 = time.time()
    d = SYNTH_DIR / scope.tenant_id
    g = scope.ops
    emb = get_embedder()
    linker = EntityLinker(scope.tenant_id, _product_names(scope))
    docs, chunks, authored, mentions = [], [], [], []
    for path in sorted((d / "docs").rglob("*.md")):
        front, paras = parse_markdown(path.read_text())
        title = paras[0].lstrip("# ").strip() if paras and paras[0].startswith("#") else front["title"]
        body = paras[1:] if paras and paras[0].startswith("#") else paras
        docs.append({"id": front["id"], "type": front["type"], "title": front["title"],
                     "uri": str(path.relative_to(ROOT)), "version": int(front.get("version", 1)),
                     "updated_at": str(front.get("updated_at", ""))})
        authored += [{"employee_id": a, "doc_id": front["id"]} for a in front.get("authors", [])]
        for n, text in enumerate(chunk_paragraphs(body)):
            cid = f"{front['id']}#{n}"
            full = f"{title}\n\n{text}" if n == 0 else text
            chunks.append({"id": cid, "doc_id": front["id"], "text": full, "ordinal": n})
            mentions += [{"src": cid, "dst": e, "confidence": c} for e, c in linker.link(full).items()]
            if n == 0:
                mentions += [{"src": cid, "dst": e, "confidence": 1.0} for e in front.get("mentions", [])]
    threads, msgs = [], []
    for path in sorted((d / "chats").glob("*.json")):
        t = json.loads(path.read_text())
        names = {e: linker.names.get(e, e).replace(" [SYNTH]", "") for e in t["authors"]}
        docs.append({"id": t["doc_id"], "type": "chat_thread", "title": f"{t['channel']}: {t['title']}",
                     "uri": str(path.relative_to(ROOT)), "version": 1, "updated_at": t["updated_at"]})
        threads.append({"id": t["id"], "channel": t["channel"], "title": t["title"], "doc_id": t["doc_id"]})
        authored += [{"employee_id": a, "doc_id": t["doc_id"]} for a in t["authors"]]
        lines = [f"{names.get(m['author'], m['author'])} ({m['ts'][:10]}): {m['text']}" for m in t["messages"]]
        for n, text in enumerate(chunk_paragraphs(lines)):
            cid = f"{t['doc_id']}#{n}"
            full = f"{t['channel']}: {t['title']}\n\n{text}" if n == 0 else text
            chunks.append({"id": cid, "doc_id": t["doc_id"], "text": full, "ordinal": n})
            mentions += [{"src": cid, "dst": e, "confidence": c} for e, c in linker.link(full).items()]
            if n == 0:
                mentions += [{"src": cid, "dst": e, "confidence": 1.0} for e in t.get("mentions", [])]
        for m in t["messages"]:
            msgs.append({"id": m["id"], "thread_id": t["id"], "author": m["author"], "ts": m["ts"], "text": m["text"]})
            mentions += [{"src": m["id"], "dst": e, "confidence": c} for e, c in linker.link(m["text"]).items()]
    for c, v in zip(chunks, emb.embed_many([c["text"] for c in chunks])):
        c["embedding"] = v
    for m, v in zip(msgs, emb.embed_many([m["text"] for m in msgs])):
        m["embedding"] = v
    g.run("load_documents", {"rows": docs})
    for i in range(0, len(chunks), 500):
        g.run("load_chunks", {"rows": chunks[i : i + 500]})
    g.run("load_authored", {"rows": authored})
    contracts = read_csv(d / "contracts.csv")
    g.run("load_contract_docs", {"rows": [{"contract_id": k["id"], "doc_id": k["doc_id"]} for k in contracts]})
    g.run("load_threads", {"rows": threads})
    for i in range(0, len(msgs), 500):
        g.run("load_chat_messages", {"rows": msgs[i : i + 500]})
    for i in range(0, len(mentions), 2000):
        g.run("load_mentions", {"rows": mentions[i : i + 2000]})
    decisions = json.loads((d / "decisions.json").read_text())
    load_decisions(scope, decisions)
    return {"documents": len(docs), "chunks": len(chunks), "messages": len(msgs), "mentions": len(mentions),
            "decisions": len(decisions), "seconds": round(time.time() - t0, 2)}


def load_decisions(scope: TenantScope, decisions: list[dict]) -> None:
    g = scope.ops
    g.run("load_decisions", {"rows": [{"id": x["id"], "summary": x["summary"], "decided_at": x["decided_at"],
                                       "status": x.get("status", "active")} for x in decisions]})
    g.run("link_decision_sources", {"rows": [{"decision_id": x["id"], "src": s} for x in decisions for s in x["sources"]]})
    g.run("link_decision_about", {"rows": [{"decision_id": x["id"], "entity": e} for x in decisions for e in x["about"]]})
    g.run("link_decision_people", {"rows": [{"decision_id": x["id"], "employee_id": e} for x in decisions
                                            for e in x.get("participants", [])]})


def linker_for(scope: TenantScope) -> EntityLinker:
    return EntityLinker(scope.tenant_id, _product_names(scope))


__all__ = ["ingest_docs", "EntityLinker", "chunk_paragraphs", "parse_markdown", "linker_for", "Path"]
