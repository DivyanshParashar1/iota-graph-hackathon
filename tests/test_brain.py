import json

from ripple.embed import get_embedder
from ripple.ingest.synth import SYNTH_DIR

PLANTED = json.loads((SYNTH_DIR / "dataco" / "planted.json").read_text())


def test_brain_ingest_counts(scope_dataco):
    q = scope_dataco.ops.query
    for label in ("Chunk", "Decision", "ChatMessage", "Document"):
        assert q(f"MATCH (n:{label}) RETURN count(n) AS c")[0]["c"] > 0
    assert q("MATCH ()-[r:MENTIONS]->() RETURN count(r) AS c")[0]["c"] > 0
    assert q("MATCH (:Decision)-[r:SOURCED_FROM]->() RETURN count(r) AS c")[0]["c"] > 0


def test_doc_search_battery_dual_source_finds_typhoon_postmortem(scope_dataco):
    qvec = get_embedder().embed("battery dual source")
    rows = scope_dataco.ops.run("doc_search", {"qvec": qvec, "k": 8, "scope": []})
    docs = []
    for r in rows:
        if r["doc_id"] not in docs:
            docs.append(r["doc_id"])
    assert PLANTED["hero"]["typhoon_postmortem"] in docs[:3], docs
