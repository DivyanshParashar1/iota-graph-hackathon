import csv
import hashlib
import json
from collections import defaultdict

import pytest

from ripple.ingest.synth import HERO_PART, HERO_SUPPLIER, SYNTH_DIR, generate


def _hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


def _csv(tenant, name):
    with open(SYNTH_DIR / tenant / f"{name}.csv") as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize("tenant", ["dataco", "nova"])
def test_generator_is_deterministic_and_matches_committed_files(tenant, tmp_path):
    a = generate(tenant, tmp_path / "a")
    b = generate(tenant, tmp_path / "b")
    ha, hb = _hashes(a), _hashes(b)
    assert ha == hb
    assert ha == _hashes(SYNTH_DIR / tenant), "committed data/synthetic is stale: run python -m ripple.ingest.synth"


@pytest.mark.parametrize("tenant", ["dataco", "nova"])
def test_shares_sum_to_one(tenant):
    tot = defaultdict(float)
    for r in _csv(tenant, "supplies"):
        tot[r["part_id"]] += float(r["share"])
    assert all(abs(v - 1.0) < 1e-6 for v in tot.values())


def test_single_sourced_ratio():
    n = defaultdict(int)
    for r in _csv("dataco", "supplies"):
        n[r["part_id"]] += 1
    ratio = sum(1 for v in n.values() if v == 1) / len(n)
    assert 0.18 <= ratio <= 0.22, ratio
    assert len(n) == len(_csv("dataco", "parts"))


def test_hero_entities_exist():
    sups = {r["name"]: r for r in _csv("dataco", "suppliers")}
    parts = {r["name"]: r for r in _csv("dataco", "parts")}
    hero_s, hero_p = sups[HERO_SUPPLIER], parts[HERO_PART]
    assert hero_s["tier"] == "1" and hero_s["country"] == "CN"
    sup = [r for r in _csv("dataco", "supplies") if r["part_id"] == hero_p["id"]]
    assert [r["supplier_id"] for r in sup] == [hero_s["id"]]  # sole supplier
    planted = json.loads((SYNTH_DIR / "dataco" / "planted.json").read_text())
    assert (SYNTH_DIR / "dataco" / "docs" / "postmortems" / f"{planted['hero']['typhoon_postmortem']}.md").exists()
    assert (SYNTH_DIR / "dataco" / "delta" / "handover.json").exists()
    assert (SYNTH_DIR / "dataco" / "chats" / "THR-001.json").exists()
    assert len(planted["chokepoints"]) == 3
    for ch in planted["chokepoints"]:
        assert len(ch["inputs"]) >= 15 and len(ch["outputs"]) >= 20
    # the disrupted parts have >= 2 qualified alternates outside China
    qual = defaultdict(list)
    ctry = {r["id"]: r["country"] for r in _csv("dataco", "suppliers")}
    for r in _csv("dataco", "qualified"):
        qual[r["part_id"]].append(r["supplier_id"])
    assert sum(ctry[x] != "CN" for x in qual[hero_p["id"]]) >= 2


def test_nova_ids_never_collide_with_dataco():
    def ids(tenant):
        out = set()
        for p in (SYNTH_DIR / tenant).glob("*.csv"):
            for r in csv.DictReader(open(p)):
                for k, v in r.items():
                    if k == "id" or k.endswith("_id"):
                        out.add(v)
        return out

    d, n = ids("dataco"), ids("nova")
    n.discard("")
    assert not (d & n)
    assert all("-N-" in x for x in n), [x for x in n if "-N-" not in x][:5]
