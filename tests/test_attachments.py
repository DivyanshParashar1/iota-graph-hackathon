"""Upload intake: parsing, profiling and storage for every supported format."""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from ripple.onboarding.attachments import (
    UnsupportedUpload,
    classify,
    ingest,
    parse,
    profile_table,
    read_table,
)

CSV = (b"name,country,lead_time_days,volume_share\n"
       b"GZ Leather,CN,30,0.6\n"
       b"Rubber Co,VN,21,0.4\n"
       b"Unknown Ltd,,45,\n")
TSV = b"name\tcountry\nGZ Leather\tCN\n"
JSONL = b'{"name": "GZ Leather", "lead": 30}\n{"name": "Rubber Co", "lead": 21}\n'
JSON_WRAPPED = json.dumps({"suppliers": [{"name": "GZ Leather"}, {"name": "Rubber Co"}]}).encode()


def test_classify():
    assert classify("suppliers.csv") == "table"
    assert classify("bom.XLSX") == "table"
    assert classify("contract.md") == "document"
    assert classify("scan.pdf") == "document"
    with pytest.raises(UnsupportedUpload):
        classify("logo.png")
    with pytest.raises(UnsupportedUpload):
        classify("noext")


def test_csv_profile():
    out = parse("suppliers.csv", CSV)
    assert out["kind"] == "table"
    p = out["profile"]
    assert p["rows"] == 3
    cols = {c["name"]: c for c in p["columns"]}
    assert set(cols) == {"name", "country", "lead_time_days", "volume_share"}
    assert cols["lead_time_days"]["min"] == 21 and cols["lead_time_days"]["max"] == 45
    assert cols["country"]["nulls"] > 0 and "CN" in cols["country"]["examples"]
    assert cols["name"]["distinct"] == 3
    assert len(p["sample"]) == 3 and p["sample"][0]["name"] == "GZ Leather"


def test_other_table_formats():
    assert read_table("x.tsv", TSV).shape == (1, 2)
    assert read_table("x.jsonl", JSONL).shape == (2, 2)
    assert list(read_table("x.json", JSON_WRAPPED)["name"]) == ["GZ Leather", "Rubber Co"]
    assert profile_table(read_table("x.tsv", TSV))["rows"] == 1


def test_markdown_document():
    out = parse("contract.md", b"# Supply agreement\n\n2% penalty per late week.   Rotterdam DC.\n")
    assert out["kind"] == "document"
    assert "2% penalty" in out["text"] and out["profile"]["chars"] > 0


def test_docx_text_extraction():
    doc = ('<?xml version="1.0"?><w:document xmlns:w="x"><w:body>'
           '<w:p><w:r><w:t>Supply agreement</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>Penalty: 2% per late week</w:t></w:r></w:p>'
           '</w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", doc)
    out = parse("contract.docx", buf.getvalue())
    assert "Supply agreement" in out["text"] and "2% per late week" in out["text"]


def test_a_broken_docx_says_so():
    with pytest.raises(UnsupportedUpload) as e:
        parse("contract.docx", b"not a zip")
    assert ".md or .txt" in str(e.value)


def test_pdf_text_extraction():
    body = b"BT /F1 12 Tf (Penalty: 2% per late week) Tj ET"
    pdf = b"%PDF-1.4\n1 0 obj\n<< /Length 50 >>\nstream\n" + body + b"\nendstream\nendobj\n%%EOF"
    out = parse("contract.pdf", pdf)
    assert "Penalty: 2% per late week" in out["text"]


def test_a_scanned_pdf_says_so():
    with pytest.raises(UnsupportedUpload) as e:
        parse("scan.pdf", b"%PDF-1.4\nstream\n\x00\x01\x02\nendstream\n%%EOF")
    assert "may be a scan" in str(e.value)


def test_ingest_stores_profiles_the_file_and_records_it(scope, tenants_dir):
    row = ingest(scope, "suppliers.csv", CSV)
    assert row["kind"] == "table" and row["bytes"] == len(CSV) and len(row["sha256"]) == 64
    assert row["profile"]["rows"] == 3
    uploads = list((tenants_dir / scope.tenant_id / "uploads").iterdir())
    assert len(uploads) == 1 and uploads[0].read_bytes() == CSV

    from ripple.onboarding.store import get_attachment, list_attachments

    stored = list_attachments(scope)
    assert len(stored) == 1 and stored[0]["filename"] == "suppliers.csv"
    assert stored[0]["profile"]["columns"][0]["name"] == "name"
    assert get_attachment(scope, row["id"])["mime"] == "text/csv"
    assert get_attachment(scope, "ATT-nope") is None


def test_ingest_writes_the_extracted_text_for_a_document(scope, tenants_dir):
    row = ingest(scope, "sop.md", b"Reroute approval needs the COO above 50k USD.")
    assert row["text_path"].endswith(".txt")
    assert "Reroute approval" in (tenants_dir / scope.tenant_id / row["text_path"]).read_text()


def test_ingest_enforces_a_size_limit(scope, tenants_dir):
    with pytest.raises(UnsupportedUpload) as e:
        ingest(scope, "big.csv", b"x" * 2048, max_mb=0)
    assert "larger than" in str(e.value)


def test_agent_context_carries_the_profile_not_the_file(scope, tenants_dir):
    from ripple.onboarding.agents.common import uploads_block

    ingest(scope, "suppliers.csv", CSV)
    block = uploads_block(scope)
    assert len(block) == 1
    as_json = json.dumps(block)
    assert "GZ Leather" in as_json  # the sample rows are there
    assert "profile" in block[0] and "text" not in block[0]
