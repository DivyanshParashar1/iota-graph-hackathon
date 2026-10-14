"""Scenario files (data/scenarios/*.yaml): load and resolve the event for a tenant. YAML only, no graph."""

from __future__ import annotations

from functools import lru_cache

import yaml

from ripple import ROOT

SCENARIO_DIR = ROOT / "data" / "scenarios"


@lru_cache
def load_scenarios() -> dict[str, dict]:
    return {p.stem: yaml.safe_load(p.read_text()) for p in sorted(SCENARIO_DIR.glob("*.yaml"))}


def scenario_event(scenario_id: str, tenant: str) -> dict:
    sc = load_scenarios()[scenario_id]
    ev = dict(sc["event"])
    ev.update((sc.get("tenant_overrides") or {}).get(tenant, {}))
    ev.setdefault("name", sc.get("name"))
    ev["scenario_id"] = scenario_id
    return ev
