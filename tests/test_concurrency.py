import sys

from ripple import ROOT

sys.path.insert(0, str(ROOT / "eval"))
from load_test import run_load_test  # noqa: E402


def test_20_sessions_two_tenants(fresh_db):
    r = run_load_test(fresh_db, sessions=20)
    assert r["errors"] == []
    assert r["leaks"] == []
    assert r["duplicates"] == 0
    for t, v in r["actions"].items():
        assert v["load_test_action_nodes"] == 1, (t, v)
    assert r["ops"] == 20 * 7
