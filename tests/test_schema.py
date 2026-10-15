import tempfile
from pathlib import Path

from ripple.db import TenantScope, close_db, get_db
from ripple.graph.schema import apply_schema, schema_statements


def test_schema_applies_twice_and_indexes_exist():
    from conftest import REMOTE

    if REMOTE:
        db = get_db(mode="remote", db_index=13)
        db.flush()
    else:
        db = get_db(Path(tempfile.mkdtemp()) / "s.db", mode="embedded")
    try:
        s = TenantScope("dataco", db)
        n1 = apply_schema(s)
        n2 = apply_schema(s)  # idempotent: no error, nothing new
        assert n1 == sum(len(v) for v in schema_statements().values())
        assert n2 == 0
        rows = s.ops.query("CALL db.indexes() YIELD label, properties RETURN label, properties")
        labels = {r["label"] for r in rows}
        assert {"Supplier", "Order", "Chunk", "ChatMessage", "Document", "Port", "Lane"} <= labels
        chunk = next(r for r in rows if r["label"] == "Chunk")
        assert "embedding" in chunk["properties"]
        mem = {r["label"] for r in s.mem.query("CALL db.indexes() YIELD label RETURN label")}
        assert {"Episode", "Fact", "Playbook"} <= mem
    finally:
        close_db(db)
