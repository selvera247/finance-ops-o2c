"""Email ACL evidence, remittance PDF/OCR extract, and digest productization."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finance_ops.copilot import service as copilot
from finance_ops.copilot.digest import build_digest_payload, run_digest
from finance_ops.copilot.email_evidence.acl import actor_may_access_customer
from finance_ops.copilot.email_evidence.adapters import FixtureMailboxAdapter
from finance_ops.copilot.email_evidence.retrieve import retrieve_email_messages
from finance_ops.copilot.remittance.extractors import (
    RemittanceExtractor,
    StubOcrProvider,
    extract_remittance_document,
)
from finance_ops.copilot.types import Decision, DecisionRequest
from pipelines.batch.ingest import ingest_batch
from scripts.load_spike_a import load as load_spike_a

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture()
def spike_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("COPILOT_MODE", "workbench")
    monkeypatch.setenv("COPILOT_EMAIL_EVIDENCE", "0")
    monkeypatch.setenv("FINANCE_OPS_DEMO_APPLY", "0")
    monkeypatch.setenv("COPILOT_DIGEST_ENABLED", "0")
    monkeypatch.setenv("COPILOT_DIGEST_SEND", "0")
    monkeypatch.setenv("COPILOT_MAILBOX_BACKEND", "fixture")
    monkeypatch.setenv("COPILOT_OCR_PROVIDER", "stub")
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.delenv("FINANCE_OPS_API_TOKEN", raising=False)
    monkeypatch.delenv("FINANCE_OPS_LOCK_WRITES", raising=False)
    monkeypatch.setattr("finance_ops.copilot.store.REPO_ROOT", tmp_path)
    monkeypatch.setattr("finance_ops.copilot.digest.REPO_ROOT", tmp_path)
    ingest_batch(run_id="copilot-email-ocr-batch")
    load_spike_a(replace_customers=True)
    sync = copilot.ensure_queue(sync=True, force=True)
    assert sync.get("synced_count", 0) >= 1
    return copilot.case_id_for_payment("PAY-1001")


def test_actor_acl_fail_closed() -> None:
    assert actor_may_access_customer("pilot-acme", "C-1042") is True
    assert actor_may_access_customer("pilot-acme", "C-2081") is False
    assert actor_may_access_customer("unknown-actor", "C-1042") is False
    assert actor_may_access_customer(None, "C-1042") is False
    assert actor_may_access_customer("reviewer", "C-2081") is True
    # Workbench UI default actor must not silently deny Mode B email.
    assert actor_may_access_customer("workbench", "C-1042") is True


def test_email_retrieve_same_customer_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPILOT_MAILBOX_BACKEND", "fixture")
    adapter = FixtureMailboxAdapter(REPO / "data/copilot/mailbox/messages.json")
    ok = retrieve_email_messages(
        customer_id="C-1042",
        payment_id="PAY-1001",
        actor="pilot",
        adapter=adapter,
    )
    assert ok["status"] == "success"
    assert ok["access_denied"] is False
    assert ok["messages"]
    assert all(m.customer_id == "C-1042" for m in ok["messages"])
    assert all(m.message_id != "MSG-OTHER-CUST" for m in ok["messages"])

    denied = retrieve_email_messages(
        customer_id="C-1042",
        payment_id="PAY-1001",
        actor="pilot-acme-nope",  # unknown → deny
        adapter=adapter,
    )
    assert denied["access_denied"] is True
    assert denied["messages"] == []


def test_email_cross_customer_never_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPILOT_MAILBOX_BACKEND", "fixture")
    adapter = FixtureMailboxAdapter(REPO / "data/copilot/mailbox/messages.json")
    # Even a reviewer must not see C-2081 mail when querying C-1042.
    out = retrieve_email_messages(
        customer_id="C-1042",
        payment_id="PAY-2001",  # payment belongs to other customer in fixtures
        actor="reviewer",
        adapter=adapter,
    )
    assert out["access_denied"] is False
    for msg in out["messages"]:
        assert msg.customer_id == "C-1042"
        assert msg.message_id != "MSG-OTHER-CUST"


def test_email_wired_into_evidence_when_enabled(
    spike_ready: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COPILOT_EMAIL_EVIDENCE", "1")
    case_id = spike_ready
    ev = copilot.get_evidence(case_id, actor="pilot")
    emails = [i for i in ev["evidence"]["items"] if i["source_type"] == "email"]
    assert emails, "expected fixture email evidence for C-1042 / PAY-1001"
    assert all(i.get("stub") is False for i in emails)
    assert all(i["fields"]["customer_id"] == "C-1042" for i in emails)

    # Unauthorized actor → no email items (fail closed), ERP evidence still present.
    denied = copilot.get_evidence(case_id, actor="stranger")
    denied_emails = [
        i for i in denied["evidence"]["items"] if i["source_type"] == "email"
    ]
    assert denied_emails == []
    assert any(i["source_type"] == "payment" for i in denied["evidence"]["items"])


def test_pdf_remittance_extract_fields() -> None:
    pdf = REPO / "data/copilot/remittance/REM-PAY-1001.pdf"
    assert pdf.is_file()
    doc = RemittanceExtractor(ocr=StubOcrProvider()).extract_path(
        pdf, payment_id="PAY-1001", customer_id="C-1042"
    )
    assert doc.method in {"pdf_text", "ocr", "plain_text"}
    assert "INV-84219" in (doc.extracted_fields.get("invoice_ids") or [])
    assert doc.extracted_fields.get("payment_id") == "PAY-1001"
    assert doc.extracted_fields.get("amount") == 1842.5
    assert doc.confidence >= 0.7
    assert doc.thin_evidence is False


def test_thin_ocr_fixture_abstains(
    spike_ready: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    thin = extract_remittance_document(
        payment_id="PAY-SCAN-THIN",
        customer_id="C-3329",
        path=REPO / "data/copilot/remittance/REM-SCAN-THIN.pdf",
    )
    assert thin is not None
    assert thin.thin_evidence is True
    assert thin.confidence < 0.45

    # Orphan PAY-3001 still abstains via investigate path.
    case_id = copilot.case_id_for_payment("PAY-3001")
    queue = copilot.list_queue(limit=100)
    if case_id not in {c["case_id"] for c in queue["cases"]}:
        pytest.skip("orphan not synced")
    inv = copilot.investigate(case_id, actor="test")
    assert inv["hypothesis"]["insufficient_data"] is True


def test_remittance_in_evidence_pack(spike_ready: str) -> None:
    case_id = spike_ready
    inv = copilot.investigate(case_id, actor="test")
    remits = [i for i in inv["evidence"]["items"] if i["source_type"] == "remittance"]
    assert remits
    fields = remits[0]["fields"]
    assert "confidence" in fields
    assert fields.get("extracted_fields", {}).get("invoice_ids") or fields.get("text")


def test_digest_off_by_default(spike_ready: str) -> None:
    payload = build_digest_payload()
    assert payload["enabled"] is False
    assert payload["status"] == "disabled"
    assert payload["items"] == []


def test_digest_quality_gates(
    spike_ready: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COPILOT_DIGEST_ENABLED", "1")
    monkeypatch.setenv("COPILOT_DIGEST_MIN_CONFIDENCE", "medium")
    # Investigate a few cases so overlays have confidence bands.
    for pay in ("PAY-1001", "PAY-3001", "PAY-4001"):
        cid = copilot.case_id_for_payment(pay)
        queue_ids = {c["case_id"] for c in copilot.list_queue(limit=100)["cases"]}
        if cid in queue_ids:
            copilot.investigate(cid, actor="test")

    payload = build_digest_payload(force=True, sync_first=False)
    assert payload["enabled"] is True
    for item in payload["items"]:
        assert item.get("confidence_band") in {"medium", "high"}
        assert item.get("confidence_band") != "insufficient"
    # Orphan / thin should land in excluded when investigated.
    excluded_ids = {e["case_id"] for e in payload.get("excluded") or []}
    orphan = copilot.case_id_for_payment("PAY-3001")
    if orphan in {c["case_id"] for c in copilot.list_queue(limit=100)["cases"]}:
        assert orphan in excluded_ids or orphan not in {
            i["case_id"] for i in payload["items"]
        }


def test_digest_cli_and_http(
    spike_ready: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.copilot_digest import main as digest_main

    monkeypatch.setenv("COPILOT_DIGEST_ENABLED", "0")
    assert digest_main(["--force", "--json"]) == 0

    result = run_digest(force=True)
    assert result["digest"]["enabled"] is True

    from finance_ops.serving import app

    client = TestClient(app)
    disabled = client.get("/v1/copilot/digest")
    assert disabled.status_code == 200
    assert disabled.json()["digest"]["enabled"] is False

    forced = client.get("/v1/copilot/digest?force=true")
    assert forced.status_code == 200
    assert forced.json()["digest"]["enabled"] is True

    status = client.get("/v1/copilot/status")
    assert status.json()["digest_enabled"] is False


def test_accept_still_guidance_only_with_email(
    spike_ready: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COPILOT_EMAIL_EVIDENCE", "1")
    case_id = spike_ready
    inv = copilot.investigate(case_id, actor="pilot")
    assert inv["status"] == "success"
    out = copilot.decide(
        case_id,
        DecisionRequest(decision=Decision.accept, actor="pilot"),
    )
    assert out["status"] == "success"
    assert out["warehouse_applied"] is False
    assert out["auto_apply_fired"] is False
