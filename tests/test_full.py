"""Full DataCo dataset (run with `pytest -m slow`)."""

import json
import os
import sys

import pytest

from ripple import ROOT
from ripple.db import TenantScope
from ripple.ingest.synth import SYNTH_DIR

sys.path.insert(0, str(ROOT / "eval"))


@pytest.mark.slow
def test_full_scenarios_exact(full_db):
    from run_scenarios import run

    print(f"\n[full] build of both tenants: {os.environ.get('RIPPLE_FULL_BUILD_SECONDS')} s")
    res = run(full_db, None, verbose=True)
    assert res["exact"] == res["total"] == 4
    for r in res["rows"]:
        assert r["orders"] >= 50 and r["wall_s"] < 60


@pytest.mark.slow
def test_full_chokepoints_and_brain(full_db):
    from run_brain_eval import run

    from ripple.tools.algos import single_points_of_failure

    s = TenantScope("dataco", full_db)
    top5 = [c["id"] for c in single_points_of_failure(s, top_k=5).data["chokepoints"]]
    planted = json.loads((SYNTH_DIR / "dataco" / "planted.json").read_text())
    assert all(c["id"] in top5 for c in planted["chokepoints"])
    assert run(s, verbose=False)["passed"] >= 18
