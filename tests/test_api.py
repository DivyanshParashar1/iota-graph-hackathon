"""The API: the whole onboarding flow driven through HTTP, with the transport stubbed at the provider."""

from __future__ import annotations

import json

from tests import factories as f
from tests.test_session import data_turn, experts_turn, interview_turn, ontology_turn


def start(client, stub, company="Acme Shoes"):
    """Start onboarding on the test's own tenant id (the client pins it as a header too)."""
    stub.load(interview_turn(brief_patch={"company": company}))
    r = client.post("/api/onboarding/start",
                    json={"company": company, "industry": "footwear", "tenant_id": client.tenant_id})
    assert r.status_code == 200, r.text
    return r.json()


def test_health_and_config(app_client):
    h = app_client.get("/api/health").json()
    assert h["ok"] and h["db_mode"] in ("embedded", "remote")
    assert h["stages"] == ["interview", "data", "ontology", "experts", "ready"]
    c = app_client.get("/api/config").json()
    assert c["configured_provider"] == "none" and c["has_llm"] is False


def test_no_tenant_until_onboarding_starts(app_client):
    assert app_client.get("/api/tenant").status_code == 404
    assert app_client.get("/api/onboarding/session").status_code == 404
    assert app_client.get("/api/ontology").status_code == 404


def test_start_creates_a_tenant_and_sets_the_cookie(app_client, stub):
    out = start(app_client, stub)
    assert out["tenant_id"] == app_client.tenant_id
    assert out["stage"] == "interview" and len(out["messages"]) == 1
    assert app_client.cookies.get("ripple_tenant") == app_client.tenant_id
    t = app_client.get("/api/tenant").json()
    assert t["name"] == "Acme Shoes" and t["stage"] == "interview"
    assert any(x["id"] == app_client.tenant_id for x in app_client.get("/api/tenants").json())


def test_start_requires_a_company(app_client, stub):
    assert app_client.post("/api/onboarding/start", json={"company": "  "}).status_code == 400


def test_bad_tenant_ids_are_rejected(app_client, stub):
    start(app_client, stub)
    assert app_client.get("/api/onboarding/session", headers={"X-Ripple-Tenant": "Bad Id"}).status_code == 400
    assert app_client.get("/api/onboarding/session", headers={"X-Ripple-Tenant": "nope"}).status_code == 404


def test_message_runs_a_turn_and_returns_the_state(app_client, stub):
    start(app_client, stub)
    stub.load(interview_turn(reply="Which ports?"))
    r = app_client.post("/api/onboarding/message", json={"text": "we make shoes"})
    assert r.status_code == 200
    body = r.json()
    assert body["messages"][-1]["text"] == "Which ports?"
    assert [m["role"] for m in body["state"]["messages"]][-2:] == ["user", "agent"]
    assert app_client.post("/api/onboarding/message", json={"text": " "}).status_code == 400


def test_session_resumes_the_whole_thread(app_client, stub):
    start(app_client, stub)
    stub.load(interview_turn(reply="Which ports?"))
    app_client.post("/api/onboarding/message", json={"text": "we make shoes"})
    state = app_client.get("/api/onboarding/session").json()
    assert [m["text"] for m in state["messages"]][-2:] == ["we make shoes", "Which ports?"]
    assert state["pending"] is None and state["progress"]["stage"] == "interview"


def test_form_autosave_submit_and_the_next_round(app_client, stub):
    start(app_client, stub)
    stub.load(interview_turn(done=True, brief_patch=f.brief().model_dump()), data_turn())
    app_client.post("/api/onboarding/message", json={"text": "that is everything"})
    state = app_client.get("/api/onboarding/session").json()
    form = state["open_form"]
    assert form["id"] == "FRM-001" and state["stage"] == "data"

    # autosave one field at a time, as the UI does
    r = app_client.post(f"/api/onboarding/forms/{form['id']}/answers",
                        json={"values": {"supplier_count": "40"}})
    assert r.status_code == 200 and r.json()["saved"][0]["value"] == 40
    state = app_client.get("/api/onboarding/session").json()
    assert state["open_form"]["id"] == "FRM-001"  # still open: an autosave is not a submit
    assert {a["field_id"]: a["value"] for a in state["answers"]} == {"supplier_count": 40}

    # submitting runs the agent's next turn, which asks a narrower second round
    stub.load(data_turn(form=f.form(title="Round 2: lanes").model_dump()))
    r = app_client.post(f"/api/onboarding/forms/{form['id']}/submit",
                        json={"values": {"tier1": [{"name": "GZ Leather"}]}})
    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert state["open_form"]["id"] == "FRM-002" and state["open_form"]["title"] == "Round 2: lanes"
    assert state["stage"] == "data"

    # the round the agent calls its last advances the stage
    stub.load(data_turn(form=None, done=True, done_reason="enough"), ontology_turn())
    r = app_client.post("/api/onboarding/forms/FRM-002/submit",
                        json={"values": {"supplier_count": 40}})
    assert r.json()["state"]["stage"] == "ontology"
    assert r.json()["state"]["open_form"] is None


def test_submit_reports_missing_required_fields(app_client, stub):
    start(app_client, stub)
    stub.load(interview_turn(done=True, brief_patch=f.brief().model_dump()), data_turn())
    app_client.post("/api/onboarding/message", json={"text": "done"})
    r = app_client.post("/api/onboarding/forms/FRM-001/submit", json={"values": {}})
    assert r.status_code == 400 and "supplier_count" in r.json()["detail"]


def test_answers_reject_unknown_fields_and_bad_values(app_client, stub):
    start(app_client, stub)
    stub.load(interview_turn(done=True, brief_patch=f.brief().model_dump()), data_turn())
    app_client.post("/api/onboarding/message", json={"text": "done"})
    r = app_client.post("/api/onboarding/forms/FRM-001/answers", json={"values": {"ghost": 1}})
    assert r.status_code == 400 and "no field 'ghost'" in r.json()["detail"]
    r = app_client.post("/api/onboarding/forms/FRM-001/answers",
                        json={"values": {"supplier_count": "about forty"}})
    assert r.status_code == 400
    assert app_client.post("/api/onboarding/forms/FRM-999/answers", json={}).status_code == 404


def test_synthesize_flags_everything_synthetic(app_client, stub):
    start(app_client, stub)
    stub.load(interview_turn(done=True, brief_patch=f.brief().model_dump()), data_turn(),
              {"values": {"supplier_count": 37, "uses_air": True, "air_share": 12,
                          "tier1": [{"name": "GZ Leather", "country": "CN", "lead_time_days": 30}]},
               "note": "assumed a mid-size manufacturer"})
    app_client.post("/api/onboarding/message", json={"text": "done"})
    r = app_client.post("/api/onboarding/forms/FRM-001/synthesize")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["synthetic"] is True
    assert {a["source"] for a in body["saved"]} == {"synthetic"}
    assert {a["confidence"] for a in body["saved"]} == {"synthetic"}
    assert app_client.get("/api/tenant").json()["has_synthetic"] is True


def test_upload_profiles_the_file(app_client, stub, tenants_dir):
    start(app_client, stub)
    csv = b"name,country,lead_time_days\nGZ Leather,CN,30\nRubber Co,VN,21\n"
    r = app_client.post("/api/onboarding/attachments",
                        files={"file": ("suppliers.csv", csv, "text/csv")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["attachment"]["kind"] == "table" and body["profile"]["rows"] == 2
    state = app_client.get("/api/onboarding/session").json()
    assert state["attachments"][0]["filename"] == "suppliers.csv"
    assert state["messages"][-1]["kind"] == "attachment"


def test_upload_rejects_an_unsupported_format(app_client, stub, tenants_dir):
    start(app_client, stub)
    r = app_client.post("/api/onboarding/attachments", files={"file": ("logo.png", b"\x89PNG", "image/png")})
    assert r.status_code == 400 and "not supported" in r.json()["detail"]


def test_goto_and_staleness_over_http(app_client, stub):
    start(app_client, stub)
    stub.load(interview_turn(done=True, brief_patch=f.brief().model_dump()), data_turn())
    app_client.post("/api/onboarding/message", json={"text": "done"})
    r = app_client.post("/api/onboarding/goto", json={"stage": "interview", "note": "we ship by rail too"})
    assert r.status_code == 200
    assert r.json()["stage"] == "interview"
    assert app_client.post("/api/onboarding/goto", json={"stage": "experts"}).status_code == 400


def test_steps_are_exposed(app_client, stub):
    start(app_client, stub)
    steps = app_client.get("/api/onboarding/steps").json()["steps"]
    assert any(s["agent"] == "interviewer" and s["kind"] == "llm" for s in steps)


# --------------------------------------------------------------------------- ontology

def at_ontology(client, stub):
    """Walk the whole flow to a drafted ontology: interview -> one form round -> spec."""
    start(client, stub)
    stub.load(interview_turn(done=True, brief_patch=f.brief().model_dump()), data_turn())
    client.post("/api/onboarding/message", json={"text": "done"})
    stub.load(data_turn(form=None, done=True, done_reason="enough"), ontology_turn())
    client.post("/api/onboarding/forms/FRM-001/submit",
                json={"values": {"supplier_count": 40, "tier1": [{"name": "GZ Leather", "country": "CN"}]}})
    return client.get("/api/ontology").json()


def test_ontology_is_served_with_a_diagram(app_client, stub):
    out = at_ontology(app_client, stub)
    assert out["row"]["status"] == "draft" and out["errors"] == []
    assert {n["id"] for n in out["diagram"]["nodes"]} == {"Supplier", "Part", "Product"}
    assert {link["type"] for link in out["diagram"]["links"]} == {"SUPPLIES", "PART_OF"}
    assert out["has_approved"] is False


def test_the_draft_can_be_edited_by_hand(app_client, stub):
    out = at_ontology(app_client, stub)
    spec = out["spec"]
    spec["types"][0]["label"] = "Vendor"
    for r in spec["relationships"]:
        if r["from"] == "Supplier":
            r["from"] = "Vendor"
    spec["indexes"] = [{"label": "Vendor", "property": "country"}]
    r = app_client.patch("/api/ontology/draft", json={"spec": spec})
    assert r.status_code == 200, r.text
    assert {n["id"] for n in r.json()["diagram"]["nodes"]} == {"Vendor", "Part", "Product"}
    assert r.json()["row"]["version"] == 2


def test_an_invalid_hand_edit_is_rejected_with_its_errors(app_client, stub):
    out = at_ontology(app_client, stub)
    spec = out["spec"]
    spec["types"][0]["label"] = "_Tenant"
    r = app_client.patch("/api/ontology/draft", json={"spec": spec})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert any("reserved" in e for e in detail["errors"])
    assert app_client.patch("/api/ontology/draft", json={"spec": {"types": "nonsense"}}).status_code == 400


def test_approval_applies_the_schema_and_loads_the_data(app_client, stub):
    at_ontology(app_client, stub)
    stub.load(f.batch().model_dump(by_alias=True) | {"notes": "from the data pack"}, experts_turn())
    r = app_client.post("/api/ontology/approve")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["types"] == 3 and body["nodes"] == 4 and body["edges"] == 3
    assert body["state"]["stage"] == "experts"
    assert body["state"]["counts"]["nodes"] == {"Supplier": 2, "Part": 1, "Product": 1}
    out = app_client.get("/api/ontology").json()
    assert out["row"]["status"] == "approved" and out["approved_version"] == 1


def test_provenance_is_answerable_over_http(app_client, stub):
    at_ontology(app_client, stub)
    app_client.post("/api/onboarding/forms/FRM-001/answers", json={"values": {"supplier_count": 40}})
    answers = app_client.get("/api/onboarding/session").json()["answers"]
    assert answers, "the data pack should hold the answer the node will be traced back to"
    stub.load(f.batch(source_ids=[a["id"] for a in answers]).model_dump(by_alias=True), experts_turn())
    app_client.post("/api/ontology/approve")
    r = app_client.get("/api/ontology/provenance/SUP-0001")
    assert r.status_code == 200
    sources = r.json()["sources"]
    assert sorted(s["source_id"] for s in sources) == sorted(a["id"] for a in answers)
    assert {s["source_label"] for s in sources} == {"_FormAnswer"}
    assert {s["source_ref"] for s in sources} == {"supplier_count", "tier1"}


# --------------------------------------------------------------------------- experts

def at_experts(client, stub, tenants_dir=None):
    at_ontology(client, stub)
    stub.load(f.batch().model_dump(by_alias=True), experts_turn())
    client.post("/api/ontology/approve")
    return client.get("/api/experts").json()


def test_roles_are_listed_after_generation(app_client, stub, tenants_dir):
    out = at_experts(app_client, stub)
    assert [e["name"] for e in out["experts"]] == ["sourcing_risk"]
    assert out["pending"] == 1 and out["approved"] == 0
    assert set(out["ontology_types"]) == {"Supplier", "Part", "Product"}


def test_approve_retire_and_delete(app_client, stub, tenants_dir):
    at_experts(app_client, stub)
    out = app_client.post("/api/experts/EXP-sourcing_risk/approve").json()
    assert out["approved"] == 1
    out = app_client.post("/api/experts/EXP-sourcing_risk/retire").json()
    assert out["experts"][0]["status"] == "retired"
    out = app_client.delete("/api/experts/EXP-sourcing_risk").json()
    assert out["experts"] == []
    assert app_client.post("/api/experts/EXP-nope/approve").status_code == 404


def test_a_role_can_be_created_and_edited_by_hand(app_client, stub, tenants_dir):
    at_experts(app_client, stub)
    role = f.role(name="customs", title="Customs Analyst",
                  justification="Classifies every Part for import duty.").model_dump()
    r = app_client.post("/api/experts", json={"role": role})
    assert r.status_code == 200, r.text
    assert r.json()["origin"] == "user" and r.json()["id"] == "EXP-customs"
    r = app_client.patch("/api/experts/EXP-customs", json={"role": {"title": "Customs Lead"}})
    assert r.json()["title"] == "Customs Lead" and r.json()["version"] == 2


def test_an_invalid_role_is_rejected(app_client, stub, tenants_dir):
    at_experts(app_client, stub)
    bad = f.role(name="ghost_expert", focus_types=["Ghost"]).model_dump()
    r = app_client.post("/api/experts", json={"role": bad})
    assert r.status_code == 400
    assert any("not in the approved ontology" in e for e in r.json()["detail"]["errors"])


def test_export_and_import_round_trip_over_http(app_client, stub, tenants_dir):
    at_experts(app_client, stub)
    files = app_client.post("/api/experts/export").json()["files"]
    assert files == ["experts/sourcing_risk.md"]
    app_client.delete("/api/experts/EXP-sourcing_risk")
    assert app_client.get("/api/experts").json()["experts"] == []
    imported = app_client.post("/api/experts/import").json()["imported"]
    assert [r["name"] for r in imported] == ["sourcing_risk"]


def test_asking_a_role_runs_the_tool_loop(app_client, stub, tenants_dir):
    at_experts(app_client, stub)
    stub.load(("", [("find_nodes", {"label": "Supplier"})]),
              "SUP-0001 and SUP-0002 both supply the sole.")
    r = app_client.post("/api/experts/EXP-sourcing_risk/ask",
                        json={"question": "who supplies the sole?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] and "SUP-0001" in body["text"]
    assert body["role"] == "sourcing_risk" and "describe_ontology" in body["tools"]
    assert sorted(body["ids"]) == ["SUP-0001", "SUP-0002"]
    # the role's own prompt is the system prompt, with the host contract appended
    system = stub.calls[0]["system"]
    assert "Sourcing Risk Analyst" in system and "## Your runtime" in system
    assert "find_nodes" in json.dumps(stub.calls[0]["tools"])
    assert app_client.post("/api/experts/EXP-sourcing_risk/ask", json={"question": ""}).status_code == 400


def test_finish_needs_an_approved_role(app_client, stub, tenants_dir):
    at_experts(app_client, stub)
    assert app_client.post("/api/experts/finish").status_code == 400
    app_client.post("/api/experts/EXP-sourcing_risk/approve")
    r = app_client.post("/api/experts/finish")
    assert r.status_code == 200
    assert r.json()["state"]["stage"] == "ready"
    assert app_client.get("/api/tenant").json()["status"] == "live"


def test_the_graph_sample_excludes_platform_nodes(app_client, stub, tenants_dir):
    at_experts(app_client, stub)
    g = app_client.get("/api/graph").json()
    assert {n["label"] for n in g["nodes"]} == {"Supplier", "Part", "Product"}
    assert {e["type"] for e in g["edges"]} == {"SUPPLIES", "PART_OF"}


def test_reonboarding_over_http(app_client, stub, tenants_dir):
    at_experts(app_client, stub)
    app_client.post("/api/experts/EXP-sourcing_risk/approve")
    app_client.post("/api/experts/finish")
    stub.load(interview_turn(reply="What changed?"))
    r = app_client.post("/api/onboarding/reonboard", json={"stage": "interview", "note": "new line"})
    assert r.status_code == 200
    assert r.json()["state"]["stage"] == "interview"
    assert app_client.get("/api/ontology").json()["row"]["stale"] is True


# --------------------------------------------------------------------------- file -> field mapping

SUPPLIERS_CSV = (b"supplier,iso,part,days,share\n"
                 b"GZ Leather,CN,soles,30,60\n"
                 b"Mekong Rubber,VN,soles,21,40\n"
                 b"Anatolia Textiles,TR,uppers,35,100\n")


def at_form(client, stub):
    start(client, stub)
    stub.load(interview_turn(done=True, brief_patch=f.brief().model_dump()), data_turn())
    client.post("/api/onboarding/message", json={"text": "done"})
    return client.get("/api/onboarding/session").json()["open_form"]


def test_a_column_answers_a_single_field(app_client, stub, tenants_dir):
    form = at_form(app_client, stub)
    att = app_client.post("/api/onboarding/attachments",
                          files={"file": ("suppliers.csv", SUPPLIERS_CSV, "text/csv")}).json()
    r = app_client.post(f"/api/onboarding/forms/{form['id']}/map",
                        json={"field_id": "supplier_count", "attachment_id": att["attachment"]["id"],
                              "column": "days"})
    assert r.status_code == 200, r.text
    saved = r.json()["saved"][0]
    assert saved["value"] == 30 and saved["source"] == "file"


def test_columns_fill_a_repeating_group(app_client, stub, tenants_dir):
    form = at_form(app_client, stub)
    att = app_client.post("/api/onboarding/attachments",
                          files={"file": ("suppliers.csv", SUPPLIERS_CSV, "text/csv")}).json()
    r = app_client.post(f"/api/onboarding/forms/{form['id']}/map",
                        json={"field_id": "tier1", "attachment_id": att["attachment"]["id"],
                              "columns": {"name": "supplier", "country": "iso", "part": "part",
                                          "lead_time_days": "days", "volume_share": "share"}})
    assert r.status_code == 200, r.text
    rows = r.json()["saved"][0]["value"]
    assert len(rows) == 3
    assert rows[0] == {"name": "GZ Leather", "country": "CN", "part": "soles", "lead_time_days": 30,
                       "volume_share": 60}
    assert {a["source"] for a in r.json()["saved"]} == {"file"}


def test_mapping_errors_are_reported(app_client, stub, tenants_dir):
    form = at_form(app_client, stub)
    att = app_client.post("/api/onboarding/attachments",
                          files={"file": ("suppliers.csv", SUPPLIERS_CSV, "text/csv")}).json()
    aid = att["attachment"]["id"]
    r = app_client.post(f"/api/onboarding/forms/{form['id']}/map",
                        json={"field_id": "supplier_count", "attachment_id": aid, "column": "ghost"})
    assert r.status_code == 400 and "no column" in r.json()["detail"]
    r = app_client.post(f"/api/onboarding/forms/{form['id']}/map",
                        json={"field_id": "ghost", "attachment_id": aid, "column": "days"})
    assert r.status_code == 400 and "no field" in r.json()["detail"]
    r = app_client.post(f"/api/onboarding/forms/{form['id']}/map",
                        json={"field_id": "tier1", "attachment_id": aid, "column": "days"})
    assert r.status_code == 400 and "needs `columns`" in r.json()["detail"]
    r = app_client.post(f"/api/onboarding/forms/{form['id']}/map",
                        json={"field_id": "supplier_count", "attachment_id": "ATT-nope", "column": "days"})
    assert r.status_code == 404


def test_a_document_cannot_be_mapped_as_a_table(app_client, stub, tenants_dir):
    form = at_form(app_client, stub)
    att = app_client.post("/api/onboarding/attachments",
                          files={"file": ("sop.md", b"Reroutes need the COO above 50k.", "text/markdown")}).json()
    r = app_client.post(f"/api/onboarding/forms/{form['id']}/map",
                        json={"field_id": "supplier_count", "attachment_id": att["attachment"]["id"],
                              "column": "days"})
    assert r.status_code == 400 and "a document, not a table" in r.json()["detail"]
