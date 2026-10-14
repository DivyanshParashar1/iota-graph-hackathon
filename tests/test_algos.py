import json

from ripple.ingest.synth import SYNTH_DIR
from ripple.tools.algos import alt_route, single_points_of_failure, supplier_clusters, supplier_influence

PLANTED = json.loads((SYNTH_DIR / "dataco" / "planted.json").read_text())


def test_planted_chokepoints_in_top5_betweenness(scope_dataco):
    r = single_points_of_failure(scope_dataco, top_k=5)
    top5 = [c["id"] for c in r.data["chokepoints"]]
    for ch in PLANTED["chokepoints"]:
        assert ch["id"] in top5, (ch["id"], top5)
    assert r.data["single_sourced_count"] > 0
    assert r.data["chokepoints"][0]["downstream_tier1"] >= 20


def test_pagerank_returns_scores(scope_dataco):
    r = supplier_influence(scope_dataco, top_k=10)
    assert len(r.data["suppliers"]) == 10 and all(s["score"] > 0 for s in r.data["suppliers"])


def test_clusters_cover_all_suppliers(scope_dataco):
    n = scope_dataco.ops.query("MATCH (s:Supplier) RETURN count(s) AS c")[0]["c"]
    r = supplier_clusters(scope_dataco)
    assert r.data["covered"] == n
    assert r.data["covered_communities"] == n


def test_alt_route_avoids_closed_port_and_is_not_shorter(scope_dataco):
    # destination stays open, transit hub closed
    r = alt_route(scope_dataco, origin_port="PORT-CNNGB", dest_port="PORT-NLRTM", avoid_ports=["PORT-SGSIN"])
    assert "PORT-SGSIN" not in r.data["route"]
    assert r.data["lane_transit_days"] >= r.data["original_transit_days"]
    # origin itself closed: route starts from the nearest open port
    r2 = alt_route(scope_dataco, origin_port="PORT-CNSHA", dest_port="PORT-USLAX", avoid_ports=["PORT-CNSHA"])
    assert r2.data["route"][0] != "PORT-CNSHA" and "PORT-CNSHA" not in r2.data["route"]
    assert r2.data["new_origin"] in ("PORT-CNNGB", "PORT-CNTAO", "PORT-CNSZX", "PORT-KRPUS")
    assert r2.data["lane_transit_days"] >= r2.data["original_transit_days"]
    assert r2.data["added_days"] >= 0
