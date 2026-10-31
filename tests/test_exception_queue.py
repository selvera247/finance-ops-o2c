"""Slice 1 — AR exception queue story + metrics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finance_ops.runtime.exception_queue import (
    STORY,
    build_ar_exception_queue,
    format_queue_markdown,
)
from finance_ops.runtime.hitl import ApprovalStore
from finance_ops.tools.queue_tools import ar_exception_queue_summary
from pipelines.batch.ingest import ingest_batch
from scripts.load_spike_a import load as load_spike_a
from scripts.load_spike_b import load as load_spike_b


@pytest.fixture()
def spikes_loaded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ApprovalStore:
    ingest_batch(run_id="queue-test-batch")
    load_spike_a(replace_customers=True)
    load_spike_b()
    store = ApprovalStore(root=tmp_path / "hitl")
    monkeypatch.setattr(
        "finance_ops.runtime.exception_queue.DEFAULT_STORE", store
    )
    monkeypatch.setattr(
        "finance_ops.runtime.hitl.DEFAULT_STORE", store
    )
    return store


def test_queue_story_and_open_metrics(spikes_loaded: ApprovalStore) -> None:
    snap = build_ar_exception_queue(store=spikes_loaded)
    assert snap["status"] == "success"
    assert snap["story"] == STORY
    assert "request_cash_app_approval" in snap["story"]
    assert snap["lanes"]["cash_app"]["entry_tool"] == "request_cash_app_approval"
    assert snap["lanes"]["portal_remittance"]["entry_tool"] == "request_portal_extract_review"

    metrics = snap["metrics"]
    assert metrics["open_exception_usd"] > 0
    assert metrics["pending_approvals"] == 0
    assert metrics["time_to_approve_seconds"]["count"] == 0

    walk_ids = {w["id"] for w in snap["lanes"]["cash_app"]["walkthrough"]}
    assert {"PAY-1001", "PAY-2001", "PAY-3001"} <= walk_ids
    portal_ids = {w["id"] for w in snap["lanes"]["portal_remittance"]["walkthrough"]}
    assert {"CLM-B1001", "CLM-B2001", "CLM-B3001"} <= portal_ids
    assert snap["needs_review"] is True


def test_pending_and_time_to_approve(spikes_loaded: ApprovalStore) -> None:
    store = spikes_loaded
    pending = store.create(
        kind="cash_app_match",
        amount=1500.0,
        summary="Cash app match: PAY-1001 → INV-84219",
        payload={"payment_id": "PAY-1001", "invoice_id": "INV-84219"},
    )
    approved = store.create(
        kind="cash_app_match",
        amount=2200.0,
        summary="Cash app match: PAY-2001 → INV-90001",
        payload={"payment_id": "PAY-2001"},
    )
    # Backdate created_at so TTA is measurable
    created = datetime.now(timezone.utc) - timedelta(seconds=90)
    approved.created_at = created.isoformat()
    store._save(approved)
    store.decide(approved.approval_id, decision="approved", actor="test")

    snap = build_ar_exception_queue(store=store)
    assert snap["metrics"]["pending_approvals"] == 1
    assert snap["metrics"]["pending_approval_usd"] == 1500.0
    tta = snap["metrics"]["time_to_approve_seconds"]
    assert tta["count"] == 1
    assert tta["median_seconds"] is not None
    assert tta["median_seconds"] >= 80
    assert pending.approval_id in {p["approval_id"] for p in snap["hitl"]["pending"]}


def test_matched_usd_after_apply(spikes_loaded: ApprovalStore) -> None:
    from data_plane import repository as repo

    before = build_ar_exception_queue(store=spikes_loaded)
    before_matched = before["metrics"]["matched_usd"]

    applied = repo.apply_payment_match("PAY-1001", "INV-84219")
    assert applied.get("ok") is True

    after = build_ar_exception_queue(store=spikes_loaded)
    assert after["metrics"]["matched_count"] == before["metrics"]["matched_count"] + 1
    assert after["metrics"]["matched_usd"] > before_matched
    pay_row = next(
        w
        for w in after["lanes"]["cash_app"]["walkthrough"]
        if w["id"] == "PAY-1001"
    )
    assert pay_row["stage"] == "applied"


def test_tool_and_markdown(spikes_loaded: ApprovalStore) -> None:
    out = ar_exception_queue_summary(include_markdown=True)
    assert out["status"] == "success"
    assert out.get("evidence")
    assert "Matched:" in (out.get("markdown") or "")
    md = format_queue_markdown(out)
    assert md.startswith("# AR exception queue")
    assert "Time-to-approve" in md


def test_http_endpoint(spikes_loaded: ApprovalStore) -> None:
    from finance_ops.serving import app

    client = TestClient(app)
    res = client.get("/v1/ar_exception_queue")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert "metrics" in body
    assert body["metrics"]["open_exception_usd"] >= 0

    res_md = client.get("/v1/ar_exception_queue", params={"markdown": "true"})
    assert res_md.status_code == 200
    assert "markdown" in res_md.json()


def test_rbac_allows_coordinator_and_payments() -> None:
    from finance_ops.governance.rbac import is_tool_allowed

    assert is_tool_allowed("finance_ops_coordinator", "ar_exception_queue_summary")[0]
    assert is_tool_allowed("payments_agent", "ar_exception_queue_summary")[0]
    assert is_tool_allowed("invoice_agent", "ar_exception_queue_summary")[0] is False
