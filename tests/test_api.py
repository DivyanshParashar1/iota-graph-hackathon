import json
import time

import pytest
from fastapi.testclient import TestClient

from ripple.api.app import create_app
from ripple.config import Settings


@pytest.fixture(scope="module")
def client(fresh_db):
    app = create_app(Settings(ripple_autobuild=False), db=fresh_db)
    with TestClient(app) as c:
        yield c


def _sse(client, url, headers=None, timeout=90):
    evs = []
    t0 = time.time()
    with client.stream("GET", url, headers=headers or {}) as r:
        assert r.status_code == 200
        for line in r.iter_lines():
            if line.startswith("data:"):
                ev = json.loads(line[5:].strip())
                evs.append(ev)
                if ev["kind"] in ("done", "error"):
                    break
            assert time.time() - t0 < timeout
    return evs


def test_meta_endpoints(client):
    h = client.get("/api/health").json()
    from conftest import REMOTE

    assert h["ok"] and h["db_mode"] == ("remote" if REMOTE else "embedded") and "tenant_dataco" in h["graphs"]
    ts = client.get("/api/tenants").json()
    assert {t["id"] for t in ts} == {"dataco", "nova"} and all(t["nodes"] > 0 for t in ts)
    o = client.get("/api/ontology").json()
    assert next(l for l in o["labels"] if l["label"] == "Order")["count"] == 3000
    m = client.get("/api/map").json()
    assert len(m["ports"]) == 26 and m["suppliers"] and m["plants"]
    assert client.get("/api/map", headers={"X-Ripple-Tenant": "acme"}).status_code == 404
    sc = client.get("/api/scenarios").json()
    assert {s["id"] for s in sc} >= {"port_closure_shanghai", "tier2_fire"}
    assert client.get("/api/people").json()
    for path in ("/api/algos/spof", "/api/algos/influence", "/api/algos/clusters"):
        assert client.get(path).status_code == 200


def test_incident_flow_sse_approve_close(client):
    r = client.post("/api/incidents", json={"scenario_id": "port_closure_shanghai"}).json()
    iid = r["incident_id"]
    assert r["mode"] in ("scripted", "scripted (no API key)")
    evs = _sse(client, f"/api/incidents/{iid}/events")
    assert evs[-1]["kind"] == "done" and len(evs) > 10
    assert {"sentinel", "analyst", "planner", "comms"} <= {e["agent"] for e in evs}
    d = client.get(f"/api/incidents/{iid}").json()
    assert d["incident"]["revenue_at_risk_initial"] > 0 and len(d["handoffs"]) == 5 and d["recalled"]
    assert any(i["id"] == iid for i in client.get("/api/incidents").json())
    g = client.get(f"/api/incidents/{iid}/graph").json()
    assert 0 < len(g["nodes"]) <= 300 and g["links"]
    assert {"source", "target", "type"} <= set(g["links"][0])
    q = client.get("/api/actions", params={"status": "proposed"}).json()
    reroute = next(a for a in q if a["type"] == "REROUTE_ORDERS" and a["incident_id"] == iid)
    a = client.get(f"/api/actions/{reroute['id']}").json()
    assert a["evidence"] and a["agent"] == "planner"
    ap = client.post(f"/api/actions/{reroute['id']}/approve", json={"user": "USR-judge"}).json()
    assert ap["status"] == "executed" and ap["revenue_after"] < ap["revenue_before"]
    u = client.post(f"/api/actions/{reroute['id']}/undo").json()
    assert u["revenue_after"] == pytest.approx(ap["revenue_before"], abs=0.01)
    ex = client.post(f"/api/actions/{reroute['id']}/execute").json()
    assert ex["noop"]  # undone actions can't be re-executed
    c = client.post(f"/api/incidents/{iid}/close").json()
    assert c["data"]["status"] == "closed"
    # replay after the bus is gone (restart): timeline comes from logged ToolCalls
    from ripple.agents.events import BUS

    BUS.reset(iid)
    client.app.state.started.discard(iid)
    rep = _sse(client, f"/api/incidents/{iid}/events")
    assert rep[-1]["kind"] == "done" and rep[-1]["data"]["replayed"]
    # a closed scenario re-triggered is a new incident
    r2 = client.post("/api/incidents", json={"scenario_id": "port_closure_shanghai"}).json()
    assert r2["incident_id"] != iid
    _sse(client, f"/api/incidents/{r2['incident_id']}/events")


def test_reject_endpoint(client):
    r = client.post("/api/incidents", json={"scenario_id": "tier2_fire"}).json()
    _sse(client, f"/api/incidents/{r['incident_id']}/events")
    q = client.get("/api/actions", params={"status": "proposed", "incident_id": r["incident_id"]}).json()
    assert q
    rj = client.post(f"/api/actions/{q[0]['id']}/reject", json={"reason": "test"}).json()
    assert rj["status"] == "rejected"


def test_brain_and_memory_endpoints(client):
    a = client.post("/api/brain/ask", json={"question": "Why did we dual-source the Li-ion battery pack?",
                                            "user_id": "USR-judge"}).json()
    assert a["sources"] and a["path"] and "why" in a["intent"]
    s = client.get("/api/brain/handover-sample").json()
    ing = client.post("/api/brain/ingest", json={"text": s["text"], "author_id": s["author_id"],
                                                 "channel": s["channel"]}).json()
    assert ing["handover"]["to"] == s["expected"]["new_owner_id"]
    assert client.get("/api/memory/episodes").json()
    assert client.get("/api/memory/playbooks").json()
    assert client.get("/api/memory/facts").json()
    assert client.get("/api/memory/facts", params={"subject_id": s["expected"]["supplier_id"]}).json()
    conv = client.get("/api/memory/conversations", params={"user_id": "USR-judge"}).json()
    assert conv and conv[0]["messages"]
    assert client.get("/api/memory/conversations").json()


def test_nova_tenant_isolated(client):
    h = {"X-Ripple-Tenant": "nova"}
    r = client.post("/api/incidents", json={"scenario_id": "port_closure_shanghai"}, headers=h).json()
    evs = _sse(client, f"/api/incidents/{r['incident_id']}/events", headers=h)
    assert evs[-1]["kind"] == "done"
    ids = [i for e in evs for i in e["node_ids"]]
    assert ids and not any(i.startswith(("ORD-", "SUP-", "PORT-")) and "-N-" not in i for i in ids)
    assert all(a["incident_id"] != r["incident_id"] for a in client.get("/api/actions").json())
