"""Production hardening — regressions for AR feed / triage debug findings."""

from __future__ import annotations

from pathlib import Path

import pytest

from data_plane.config import INCOMING_DIR
from finance_ops.runtime.ar_feed import (
    ingest_erp_payment_csv,
    open_hitl_for_ready,
    stage_sample_erp_feed,
    triage_unmatched_payments,
)
from finance_ops.runtime.hitl import ApprovalStore
from finance_ops.tools.queue_tools import start_ar_exception_triage
from pipelines.batch.ingest import ingest_batch
from scripts.load_spike_a import load as load_spike_a


@pytest.fixture()
def warehouse_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ApprovalStore:
    ingest_batch(run_id="dbg-harden-batch")
    load_spike_a(replace_customers=True)
    store = ApprovalStore(root=tmp_path / "hitl")
    monkeypatch.setattr("finance_ops.runtime.hitl.DEFAULT_STORE", store)
    monkeypatch.setattr("finance_ops.runtime.exception_queue.DEFAULT_STORE", store)
    return store


def test_run_ids_unique_under_rapid_fire(warehouse_ready: ApprovalStore) -> None:
    ids = [
        start_ar_exception_triage(
            stage_sample=True, request_hitl=False, use_live_hubspot=False
        )["run_id"]
        for _ in range(5)
    ]
    assert len(ids) == len(set(ids))
    assert all(rid.startswith("WF-AR-TRIAGE-") for rid in ids)


def test_empty_drop_zone_does_not_autostage(warehouse_ready: ApprovalStore) -> None:
    drop = INCOMING_DIR / "ar_exceptions"
    drop.mkdir(parents=True, exist_ok=True)
    for f in drop.glob("*.csv"):
        f.unlink()
    out = ingest_erp_payment_csv(auto_stage_sample=False)
    assert out["status"] == "error"
    assert out["count"] == 0


def test_corrupt_csv_reports_row_errors_not_crash(warehouse_ready: ApprovalStore) -> None:
    drop = INCOMING_DIR / "ar_exceptions"
    drop.mkdir(parents=True, exist_ok=True)
    bad = drop / "corrupt_feed.csv"
    bad.write_text(
        "payment_id,customer_id,amount,currency,status,reference,received_at\n"
        ",C-1042,10,USD,unmatched,x,2026-10-01\n"
        "PAY-BAD-AMT,C-1042,not-a-number,USD,unmatched,x,2026-10-01\n"
        "PAY-OK-99,C-1042,12.50,USD,unmatched,Remittance INV-84219,2026-10-01\n",
        encoding="utf-8",
    )
    out = ingest_erp_payment_csv(bad)
    assert out["status"] == "success"
    assert "PAY-OK-99" in out["payment_ids"]
    errs = {e["error"] for e in out["row_errors"]}
    assert "missing_payment_id" in errs
    assert "invalid_amount" in errs


def test_hitl_ready_requires_amount_tolerance(warehouse_ready: ApprovalStore) -> None:
    """invoice+PO without amount must not open HITL (score can still be >= 1.0)."""
    stage_sample_erp_feed()
    ingest_erp_payment_csv()
    triage = triage_unmatched_payments(payment_ids=["PAY-FEED-01", "PAY-FEED-02"])
    ready_ids = {r["payment_id"] for r in triage["ready_for_hitl"]}
    assert "PAY-FEED-01" in ready_ids  # INV in ref + amount match
    assert "PAY-FEED-02" not in ready_ids  # weak score / no amount gate
    for item in triage["ready_for_hitl"]:
        assert "amount_within_tolerance" in item["reasons"]
        assert "invoice_id_in_reference" in item["reasons"]


def test_hitl_dedupes_pending_pairs(warehouse_ready: ApprovalStore) -> None:
    stage_sample_erp_feed()
    ingest_erp_payment_csv()
    triage = triage_unmatched_payments(payment_ids=["PAY-FEED-01"])
    ready = triage["ready_for_hitl"]
    assert ready
    first = open_hitl_for_ready(ready, notify_slack=False)
    assert first["opened_count"] == 1
    second = open_hitl_for_ready(ready, notify_slack=False)
    assert second["opened_count"] == 0
    assert second["skipped_count"] == 1
    assert second["skipped"][0]["reason"] == "pending_approval_exists"


def test_bulk_score_does_not_trip_breaker(warehouse_ready: ApprovalStore) -> None:
    from finance_ops.runtime.circuit_breaker import DEFAULT_BREAKER
    from finance_ops.tools.payment_tools import score_payment_match

    DEFAULT_BREAKER.reset()
    DEFAULT_BREAKER.max_tool_calls = 3
    # Pure scoring must not increment the breaker.
    for _ in range(10):
        score_payment_match("PAY-1001")
    assert DEFAULT_BREAKER.snapshot()["tool_calls"] == 0
    DEFAULT_BREAKER.max_tool_calls = 25
