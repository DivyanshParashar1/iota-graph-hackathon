"""Every graph/queries/*.cypher file parses and runs with its documented example params (on a scratch copy of
the tenant graphs, so write queries don't touch the test DB)."""

import pytest

from ripple.embed import get_embedder
from ripple.graph.queries import all_queries

QUERIES = all_queries()


def _params(p):
    out = {}
    for k, v in p.items():
        out[k] = get_embedder().embed(v.split(":", 1)[1]) if isinstance(v, str) and v.startswith("$embed:") else v
    return out


@pytest.fixture(scope="module")
def scratch(built_db):
    from conftest import REMOTE, remote_db

    if REMOTE:  # GRAPH.COPY is unreliable on the server image under load: use a throwaway database instead
        from ripple.db import close_db

        db = remote_db(12)
        yield {"ops": db.graph("tenant_dataco")._g, "mem": db.graph("mem_dataco")._g}
        db.flush()
        close_db(db)
        return
    ops = built_db.graph("tenant_dataco")._g.copy("scratch_ops")
    mem = built_db.graph("mem_dataco")._g.copy("scratch_mem")
    yield {"ops": ops, "mem": mem}
    ops.delete()
    mem.delete()


def test_every_query_has_a_header():
    assert len(QUERIES) > 40
    for name, q in QUERIES.items():
        assert q.purpose, name
        assert q.kind in ("read", "write", "algo"), name
        assert q.graph in ("ops", "mem"), name


@pytest.mark.parametrize("name", sorted(QUERIES))
def test_query_runs(name, scratch):
    q = QUERIES[name]
    scratch[q.graph].query(q.text, _params(q.params))
