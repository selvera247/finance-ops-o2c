"""Copilot MVP foundation — guidance-only decisions, modes, RBAC regression."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finance_ops.copilot import service as copilot
from finance_ops.copilot.config import copilot_mode, demo_apply_enabled
from finance_ops.copilot.types import Decision, DecisionRequest, HypothesisUpdate, MatchLine
from finance_ops.governance.rbac import is_tool_allowed
from pipelines.batch.ingest import ingest_batch
from scripts.load_spike_a import load as load_spike_a


@pytest.fixture()
def spike_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("COPILOT_MODE", "workbench")
    monkeypatch.setenv("COPILOT_EMAIL_EVIDENCE", "0")
    monkeypatch.setenv("FINANCE_OPS_DEMO_APPLY", "0")
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.delenv("FINANCE_OPS_API_TOKEN", raising=False)
    monkeypatch.delenv("FINANCE_OPS_LOCK_WRITES", raising=False)
    # Isolate Copilot overlays
    monkeypatch.setattr(
        "finance_ops.copilot.store.REPO_ROOT",
        tmp_path,
    )
    ingest_batch(run_id="copilot-mvp-batch")
    load_spike_a(replace_customers=True)
    sync = copilot.ensure_queue(sync=True)
    assert sync.get("synced_count", 0) >= 1
    return copilot.case_id_for_payment("PAY-1001")


def test_decision_emits_guidance_without_apply(spike_ready: str) -> None:
    case_id = spike_ready
    inv = copilot.investigate(case_id, actor="test")
    assert inv["status"] == "success"
    assert inv["hypothesis"]["lines"]
    assert inv["hypothesis"]["citation_map"]
    assert demo_apply_enabled() is False

    out = copilot.decide(
        case_id,
        DecisionRequest(decision=Decision.accept, actor="test"),
    )
    assert out["status"] == "success"
    assert out["warehouse_applied"] is False
    assert out["auto_apply_fired"] is False
    assert out["case_status"] == "ready_to_apply"
    guidance = out["guidance"]
    assert guidance["payment_id"] == "PAY-1001"
    assert "INV-84219" in guidance["invoice_ids"]
    assert guidance["copy_text"]
    assert "ApplyGuidance" in guidance["copy_text"] or "GUIDANCE" in guidance["copy_text"]


def test_demo_flag_can_apply(spike_ready: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FINANCE_OPS_DEMO_APPLY", "1")
    case_id = copilot.case_id_for_payment("PAY-1002")
    # Ensure case exists
    queue = copilot.list_queue(limit=100)
    ids = {c["case_id"] for c in queue["cases"]}
    if case_id not in ids:
        pytest.skip("PAY-1002 not in synced queue")

    inv = copilot.investigate(case_id, actor="test")
    assert inv["status"] == "success"
    # Force a line if rules found none
    if not inv["hypothesis"]["lines"]:
        copilot.update_hypothesis(
            case_id,
            HypothesisUpdate(
                lines=[MatchLine(invoice_id="INV-84219", amount=2490.0)],
                confidence_band="medium",
            ),
            actor="test",
        )

    out = copilot.decide(
        case_id,
        DecisionRequest(decision=Decision.edit_ready_to_apply, actor="test"),
    )
    assert out["status"] == "success"
    assert out["warehouse_applied"] is True
    assert out["auto_apply_fired"] is False
    assert out["guidance"]["warehouse_applied"] is True


def test_rules_only_skips_llm_path(
    spike_ready: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COPILOT_MODE", "rules_only")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert copilot_mode() == "rules_only"
    case_id = spike_ready
    inv = copilot.investigate(case_id, actor="test")
    assert inv["status"] == "success"
    assert inv["rules_only"] is True
    assert inv["summary"]["rules_only"] is True
    assert inv["llm_skipped"] is True
    assert (
        "Rules-only" in inv["summary"]["summary"]
        or inv["hypothesis"]["model_id"] == "rules_only"
    )


def test_hypothesis_citations_map_to_evidence(spike_ready: str) -> None:
    case_id = spike_ready
    inv = copilot.investigate(case_id, actor="test")
    assert inv["status"] == "success"
    evidence_ids = {i["source_id"] for i in inv["evidence"]["items"]}
    for cite in inv["hypothesis"]["citation_map"]:
        assert cite["source_id"] in evidence_ids


def test_reject_requires_reason(spike_ready: str) -> None:
    case_id = spike_ready
    bad = copilot.decide(
        case_id,
        DecisionRequest(decision=Decision.reject, actor="test"),
    )
    assert bad["status"] == "error"
    assert "reason_code" in bad["error"]

    ok = copilot.decide(
        case_id,
        DecisionRequest(
            decision=Decision.reject,
            actor="test",
            reason_code="reject_other",
        ),
    )
    assert ok["status"] == "success"
    assert ok["case_status"] == "closed_rejected"
    assert ok["guidance"] is None
    assert ok["warehouse_applied"] is False


def test_rbac_still_denies_coordinator_write_tools() -> None:
    for tool in (
        "apply_payment_match",
        "request_cash_app_approval",
        "decide_approval",
    ):
        ok, reason = is_tool_allowed("finance_ops_coordinator", tool)
        assert ok is False, tool


def test_http_copilot_routes(spike_ready: str) -> None:
    from finance_ops.serving import app

    client = TestClient(app)
    status = client.get("/v1/copilot/status")
    assert status.status_code == 200
    assert status.json()["guidance_only"] is True

    health = client.get("/health")
    assert health.json()["product_north_star"] == "cash_application_exception_copilot"

    queue = client.get("/v1/copilot/queue")
    assert queue.status_code == 200
    assert queue.json()["count"] >= 1

    case_id = spike_ready
    got = client.get(f"/v1/copilot/cases/{case_id}")
    assert got.status_code == 200

    inv = client.post(f"/v1/copilot/cases/{case_id}/investigate", json={})
    assert inv.status_code == 200
    assert inv.json()["hypothesis"]["citation_map"]

    ev = client.get(f"/v1/copilot/cases/{case_id}/evidence")
    assert ev.status_code == 200
    assert ev.json()["evidence"]["items"]

    # Need-info path (does not consume accept)
    need = client.post(
        f"/v1/copilot/cases/{case_id}/decision",
        json={
            "decision": "need_info",
            "reason_code": "need_info_remittance",
            "actor": "http-test",
        },
    )
    assert need.status_code == 200
    assert need.json()["case_status"] == "need_info"
    assert need.json()["warehouse_applied"] is False

    audit = client.get(f"/v1/copilot/cases/{case_id}/audit")
    assert audit.status_code == 200
    assert len(audit.json()["audit"]) >= 1

    page = client.get("/copilot")
    assert page.status_code == 200
    assert "Exception Copilot" in page.text


def test_email_stub_when_enabled(
    spike_ready: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COPILOT_EMAIL_EVIDENCE", "1")
    case_id = spike_ready
    ev = copilot.get_evidence(case_id)
    types = {i["source_type"] for i in ev["evidence"]["items"]}
    assert "email" in types
    assert ev["evidence"]["email_enabled"] is True


def test_insufficient_data_blocks_accept(
    spike_ready: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_id = copilot.case_id_for_payment("PAY-3001")  # orphan
    queue = copilot.list_queue(limit=100)
    if case_id not in {c["case_id"] for c in queue["cases"]}:
        pytest.skip("orphan not synced")
    inv = copilot.investigate(case_id, actor="test")
    assert inv["hypothesis"]["insufficient_data"] is True
    out = copilot.decide(
        case_id,
        DecisionRequest(decision=Decision.accept, actor="test"),
    )
    assert out["status"] == "error"
    assert "insufficient" in out["error"]
