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


def test_autofill_drafts_an_answer_without_sending_it(app_client, stub):
    start(app_client, stub)
    before = app_client.get("/api/onboarding/session").json()["messages"]
    stub.load({"text": "We make about 2M pairs a year in Vietnam and Portugal.", "note": "assumed two plants"})
    r = app_client.post("/api/onboarding/autofill")
    assert r.status_code == 200, r.text
    assert r.json() == {"text": "We make about 2M pairs a year in Vietnam and Portugal.",
                        "note": "assumed two plants", "synthetic": True}
    assert app_client.get("/api/onboarding/session").json()["messages"] == before  # drafted, not sent
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


# --------------------------------------------------------------------------- objects

def at_approved(client, stub):
    at_ontology(client, stub)
    stub.load(f.batch().model_dump(by_alias=True), experts_turn())
    assert client.post("/api/ontology/approve").status_code == 200


def test_objects_of_a_type_are_listed_and_searched(app_client, stub):
    at_approved(app_client, stub)
    out = app_client.get("/api/objects/Supplier").json()
    assert out["total"] == 2 and out["title_property"] == "name"
    assert [o["id"] for o in out["objects"]] == ["SUP-0001", "SUP-0002"]
    assert out["objects"][0]["title"] == "GZ Leather" and out["objects"][0]["properties"]["country"] == "CN"
    hits = app_client.get("/api/objects/Supplier", params={"q": "rubber"}).json()["objects"]
    assert [o["id"] for o in hits] == ["SUP-0002"]


def test_an_object_opens_with_its_links(app_client, stub):
    at_approved(app_client, stub)
    out = app_client.get("/api/objects/Part/PRT-0001").json()
    assert out["title"] == "Sole"
    links = {(lk["type"], lk["direction"], lk["label"]): [o["id"] for o in lk["objects"]] for lk in out["links"]}
    assert links == {("SUPPLIES", "in", "Supplier"): ["SUP-0001", "SUP-0002"],
                     ("PART_OF", "out", "Product"): ["PRD-0001"]}
    assert app_client.get("/api/objects/Part/PRT-9999").status_code == 404


def test_global_object_search_spans_types(app_client, stub):
    at_approved(app_client, stub)
    hits = app_client.get("/api/objects/search", params={"q": "o"}).json()["hits"]
    assert {(h["label"], h["id"]) for h in hits} >= {("Supplier", "SUP-0002"), ("Part", "PRT-0001")}


def test_objects_only_open_approved_types(app_client, stub):
    at_ontology(app_client, stub)
    assert app_client.get("/api/objects/Supplier").status_code == 404  # drafted, not approved
    stub.load(f.batch().model_dump(by_alias=True), experts_turn())
    assert app_client.post("/api/ontology/approve").status_code == 200
    assert app_client.get("/api/objects/Nope").status_code == 404
    assert app_client.get("/api/objects/_Tenant").status_code == 404
    assert app_client.get("/api/objects/_Tenant/x").status_code == 404


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
    again = app_client.post("/api/experts/finish")  # a second click on a live tenant is a no-op
    assert again.status_code == 200 and again.json()["state"]["stage"] == "ready" and again.json()["messages"] == []


def test_overview_reads_hot_spots_off_the_approved_spec(app_client, stub, tenants_dir):
    at_experts(app_client, stub)
    out = app_client.get("/api/overview").json()
    assert out["has_ontology"] and out["types"] == 3 and out["relationships"] == 2
    assert out["counts"]["nodes"] == {"Supplier": 2, "Part": 1, "Product": 1}
    # PRT-0001 has two suppliers (no concentration); PRD-0001 is built from a single part
    assert [(h["rel"], h["single"], h["total"]) for h in out["hotspots"]] == [("PART_OF", 1, 1)]
    assert out["hotspots"][0]["sample"] == [{"id": "PRD-0001", "title": "Runner"}]
    assert out["incidents"]["total"] == 0 and out["experts"]


def test_overview_without_an_ontology_is_empty(app_client, stub):
    start(app_client, stub)
    out = app_client.get("/api/overview").json()
    assert out["has_ontology"] is False and out["hotspots"] == [] and out["stage"] == "interview"


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


def test_start_refuses_when_no_provider_is_configured(app_client, stub):
    """A turn that fails mid-session is reported in the thread; a tenant that could never take its first turn
    should not be created at all."""
    from ripple.llm.base import set_client

    set_client(None)  # the stub fixture installed one; this is what a real deployment with no key looks like
    try:
        r = app_client.post("/api/onboarding/start", json={"company": "No Key Co"})
    finally:
        set_client(stub)
    assert r.status_code == 503 and "no LLM provider" in r.json()["detail"]
    assert app_client.get("/api/tenants").json() == []


# --------------------------------------------------------------------------- onboarding review fixes

def at_data(client, stub):
    start(client, stub)
    stub.load(interview_turn(done=True, brief_patch=f.brief().model_dump()), data_turn())
    client.post("/api/onboarding/message", json={"text": "done"})


def test_a_submitted_form_cannot_be_submitted_again(app_client, stub):
    at_data(app_client, stub)
    stub.load(data_turn(form=f.form(title="Round 2").model_dump()))
    values = {"supplier_count": 40, "tier1": [{"name": "GZ Leather"}]}
    assert app_client.post("/api/onboarding/forms/FRM-001/submit", json={"values": values}).status_code == 200
    r = app_client.post("/api/onboarding/forms/FRM-001/submit", json={"values": values})
    assert r.status_code == 409 and "already submitted" in r.json()["detail"]
    assert len(stub.calls) == 1, "a second submit must not run a second data-agent turn"


def test_synthesize_keeps_the_values_it_can_use(app_client, stub):
    at_data(app_client, stub)
    stub.load({"values": {"supplier_count": "about forty", "uses_air": True}, "note": ""})
    r = app_client.post("/api/onboarding/forms/FRM-001/synthesize")
    assert r.status_code == 200, r.text
    assert [a["field_id"] for a in r.json()["saved"]] == ["uses_air"]


def test_a_bad_value_names_its_field(app_client, stub):
    at_data(app_client, stub)
    r = app_client.post("/api/onboarding/forms/FRM-001/answers", json={"values": {"supplier_count": [1, 2]}})
    assert r.status_code == 400 and "supplier_count" in r.json()["detail"]


def test_upload_reports_a_file_it_cannot_parse(app_client, stub, tenants_dir):
    start(app_client, stub)
    r = app_client.post("/api/onboarding/attachments", files={"file": ("suppliers.json", b"{not json", "text/json")})
    assert r.status_code == 400 and "could not read suppliers.json" in r.json()["detail"]


def test_a_second_turn_waits_for_the_first(app_client, stub):
    from ripple.onboarding.events import BUS

    start(app_client, stub)
    before = len(app_client.get("/api/onboarding/session").json()["messages"])
    BUS.enter(app_client.tenant_id)
    try:
        r = app_client.post("/api/onboarding/message", json={"text": "hello again"})
        assert r.status_code == 409
        assert app_client.post("/api/onboarding/goto", json={"stage": "interview"}).status_code == 400
    finally:
        BUS.leave(app_client.tenant_id)
    assert len(app_client.get("/api/onboarding/session").json()["messages"]) == before, \
        "a refused turn must not leave an unanswered message behind"


def test_approve_and_finish_check_the_stage(app_client, stub, tenants_dir):
    at_data(app_client, stub)
    r = app_client.post("/api/ontology/approve")
    assert r.status_code == 409 and "data stage" in r.json()["detail"]


def test_finish_needs_the_experts_stage(app_client, stub, tenants_dir):
    roles = at_experts(app_client, stub)
    app_client.post(f"/api/experts/{roles['experts'][0]['id']}/approve")
    app_client.post("/api/onboarding/goto", json={"stage": "ontology"})
    r = app_client.post("/api/experts/finish")
    assert r.status_code == 409 and "ontology stage" in r.json()["detail"]


def test_file_mappings_survive_a_new_form_round(app_client, stub):
    start(app_client, stub)
    mapping = {"field_id": "supplier_count", "attachment_id": "ATT-1", "column": "n"}
    stub.load(interview_turn(done=True, brief_patch=f.brief().model_dump()), data_turn(file_mappings=[mapping]))
    app_client.post("/api/onboarding/message", json={"text": "done"})
    msg = app_client.get("/api/onboarding/session").json()["messages"][-1]
    assert msg["kind"] == "form" and msg["payload"]["file_mappings"][0]["column"] == "n"


def test_going_back_to_the_interview_retires_the_open_form(app_client, stub):
    at_data(app_client, stub)
    assert app_client.get("/api/onboarding/session").json()["open_form"]["id"] == "FRM-001"
    app_client.post("/api/onboarding/goto", json={"stage": "interview"})
    assert app_client.get("/api/onboarding/session").json()["open_form"] is None
    # back in the data stage the agent can ask a fresh round against the new brief
    stub.load(interview_turn(done=True, brief_patch=f.brief().model_dump()),
              data_turn(form=f.form(title="Round 1, again").model_dump()))
    app_client.post("/api/onboarding/message", json={"text": "rail too; that is all"})
    assert app_client.get("/api/onboarding/session").json()["open_form"]["title"] == "Round 1, again"


def test_a_regenerated_role_set_withdraws_the_drafts_it_left_out(app_client, stub, tenants_dir):
    at_experts(app_client, stub)
    other = f.role(name="lane_planner", title="Lane Planner").model_dump()
    stub.load(experts_turn(roles=[other]))
    app_client.post("/api/onboarding/message", json={"text": "replace sourcing with a lane planner"})
    assert [r["name"] for r in app_client.get("/api/experts").json()["experts"]] == ["lane_planner"]


def test_reapproving_clears_the_stale_flag_and_keeps_a_live_stage(app_client, stub, tenants_dir):
    roles = at_experts(app_client, stub)
    app_client.post(f"/api/experts/{roles['experts'][0]['id']}/approve")
    app_client.post("/api/experts/finish")
    stub.load(f.batch().model_dump(by_alias=True))
    r = app_client.post("/api/ontology/approve")
    assert r.status_code == 200, r.text
    assert r.json()["state"]["stage"] == "ready", "re-approving on a live tenant must not reopen onboarding"
    assert app_client.get("/api/ontology").json()["row"]["stale"] is False
    assert all(e["stale"] for e in app_client.get("/api/experts").json()["experts"])


# --------------------------------------------------------------------------- workspace (employees + orchestrator)

def at_workspace(client, stub, tenants_dir):
    roles = at_experts(client, stub, tenants_dir)
    rid = roles["experts"][0]["id"]
    client.post(f"/api/experts/{rid}/approve")
    emp = client.post("/api/workspace/employees", json={"name": "Maya Chen", "title": "Sourcing lead",
                                                        "role_ids": [rid]})
    assert emp.status_code == 200, emp.text
    return emp.json(), rid


def test_employees_are_assigned_known_roles(app_client, stub, tenants_dir):
    emp, rid = at_workspace(app_client, stub, tenants_dir)
    listed = app_client.get("/api/workspace/employees").json()["employees"]
    assert [(e["name"], [r["id"] for r in e["roles"]]) for e in listed] == [("Maya Chen", [rid])]
    bad = app_client.post("/api/workspace/employees", json={"name": "X", "role_ids": ["EXP-nope"]})
    assert bad.status_code == 400
    dash = app_client.get(f"/api/workspace/employees/{emp['id']}/dashboard").json()
    assert dash["employee"]["name"] == "Maya Chen" and [r["id"] for r in dash["roles"]] == [rid]
    assert set(dash["focus_types"]) <= {"Supplier", "Part", "Product"} and dash["threads"] == []
    assert app_client.delete(f"/api/workspace/employees/{emp['id']}").status_code == 200
    assert app_client.get("/api/workspace/employees").json()["employees"] == []


def test_the_orchestrator_deploys_experts_and_cites_their_ids(app_client, stub, tenants_dir):
    emp, _ = at_workspace(app_client, stub, tenants_dir)
    stub.load(
        ("", [("consult_experts", {"asks": [{"expert": "sourcing_risk", "question": "Who supplies the sole?"}]})]),
        ("", [("find_nodes", {"label": "Supplier"})]),
        "GZ Leather (SUP-0001) and Rubber Co (SUP-0002) supply it.",
        "Two suppliers, SUP-0001 and SUP-0002, according to the Sourcing Risk Analyst.",
    )
    r = app_client.post(f"/api/workspace/employees/{emp['id']}/chat", json={"text": "Who supplies our sole?"})
    assert r.status_code == 200, r.text
    user, reply = r.json()["messages"]
    assert user["role"] == "user" and reply["role"] == "assistant"
    assert "SUP-0001" in reply["text"] and reply["payload"]["ok"] is True
    [d] = reply["payload"]["delegations"]
    assert d["expert"] == "sourcing_risk" and d["ok"] and set(d["ids"]) >= {"SUP-0001", "SUP-0002"}
    tid = r.json()["thread"]["id"]
    thread = app_client.get(f"/api/workspace/employees/{emp['id']}/threads/{tid}").json()
    assert [m["role"] for m in thread["messages"]] == ["user", "assistant"] and thread["running"] is False
    assert app_client.get(f"/api/workspace/employees/{emp['id']}/threads").json()["threads"][0]["id"] == tid


def test_the_orchestrator_cannot_cite_ids_no_expert_returned(app_client, stub, tenants_dir):
    emp, _ = at_workspace(app_client, stub, tenants_dir)
    stub.load("SUP-9999 is your only supplier.")
    reply = app_client.post(f"/api/workspace/employees/{emp['id']}/chat", json={"text": "hi"}).json()["messages"][1]
    assert reply["payload"]["ok"] is False and reply["payload"]["delegations"] == []


def test_a_tenant_can_be_deleted_with_its_files(app_client, stub, tenants_dir):
    start(app_client, stub)
    tid = app_client.tenant_id
    (tenants_dir / tid).mkdir(parents=True)
    (tenants_dir / tid / "note.txt").write_text("x")
    assert tid in [t["id"] for t in app_client.get("/api/tenants").json()]
    assert app_client.delete(f"/api/tenant/{tid}").json() == {"deleted": tid}
    assert tid not in [t["id"] for t in app_client.get("/api/tenants").json()]
    assert not (tenants_dir / tid).exists()
    assert app_client.delete(f"/api/tenant/{tid}").status_code == 404
    assert app_client.delete("/api/tenant/Bad-Id").status_code == 400
