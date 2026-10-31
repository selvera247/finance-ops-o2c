"""Slice 2 — live AR feed → durable exception triage."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finance_ops.runtime.ar_feed import (
    ingest_erp_payment_csv,
    stage_sample_erp_feed,
    triage_hubspot_gaps,
    triage_unmatched_payments,
)
from finance_ops.runtime.hitl import ApprovalStore
from finance_ops.tools.queue_tools import start_ar_exception_triage
from pipelines.batch.ingest import ingest_batch
from scripts.load_spike_a import load as load_spike_a


@pytest.fixture()
def warehouse_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ApprovalStore:
    ingest_batch(run_id="ar-feed-test-batch")
    load_spike_a(replace_customers=True)
    store = ApprovalStore(root=tmp_path / "hitl")
    monkeypatch.setattr("finance_ops.runtime.hitl.DEFAULT_STORE", store)
    monkeypatch.setattr("finance_ops.runtime.exception_queue.DEFAULT_STORE", store)
    return store


def test_stage_and_ingest_erp_feed(warehouse_ready: ApprovalStore) -> None:
    staged = stage_sample_erp_feed()
    assert staged["status"] == "success"
    out = ingest_erp_payment_csv()
    assert out["status"] == "success"
    assert out["count"] >= 3
    assert "PAY-FEED-01" in out["payment_ids"]

    from data_plane import repository as repo

    row = repo.get_payment("PAY-FEED-01")
    assert row is not None
    assert row["status"] == "unmatched"


def test_triage_suggests_high_confidence(warehouse_ready: ApprovalStore) -> None:
    stage_sample_erp_feed()
    ingest_erp_payment_csv()
    triage = triage_unmatched_payments(payment_ids=["PAY-FEED-01"])
    assert triage["status"] == "success"
    assert triage["ready_count"] >= 1
    ready = triage["ready_for_hitl"][0]
    assert ready["payment_id"] == "PAY-FEED-01"
    assert ready["invoice_id"] == "INV-84219"


def test_hubspot_gap_fixture_path(warehouse_ready: ApprovalStore) -> None:
    gaps = triage_hubspot_gaps(
        customer_ids=["C-1042", "C-2099"],
        use_live_hubspot=False,
    )
    assert gaps["status"] == "success"
    assert gaps["mode"] == "fixture"
    assert gaps["gap_count"] >= 1
    custs = {g["customer_id"] for g in gaps["gaps"]}
    assert "C-1042" in custs or "C-2099" in custs


def test_durable_triage_end_to_end(warehouse_ready: ApprovalStore) -> None:
    result = start_ar_exception_triage(
        stage_sample=True,
        request_hitl=False,
        use_live_hubspot=False,
    )
    assert result["status"] == "success"
    assert result["run_id"].startswith("WF-AR-TRIAGE-")
    assert result["feed_ingest"]["count"] >= 3
    assert result["cash_app_triage"]["ready_count"] >= 1
    assert result["hubspot_gaps"]["gap_count"] >= 1
    assert result["queue_metrics"] is not None
    assert "open_exception_usd" in result["queue_metrics"]
    # Never silently applied
    assert result.get("hitl_opened") is None or result["hitl_opened"].get("skipped")


def test_durable_triage_optional_hitl(warehouse_ready: ApprovalStore) -> None:
    result = start_ar_exception_triage(
        stage_sample=True,
        request_hitl=True,
        notify_slack=False,
        use_live_hubspot=False,
    )
    assert result["status"] == "success"
    opened = result.get("hitl_opened") or {}
    assert opened.get("opened_count", 0) >= 1
    assert any(o.get("status") == "pending" for o in opened.get("opened") or [])


def test_http_triage_endpoint(warehouse_ready: ApprovalStore) -> None:
    from finance_ops.serving import app

    client = TestClient(app)
    res = client.post(
        "/v1/ar_exception_triage",
        json={
            "stage_sample": True,
            "request_hitl": False,
            "use_live_hubspot": False,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert body["run_id"]


def test_rbac_triage_tools() -> None:
    from finance_ops.governance.rbac import is_tool_allowed

    assert is_tool_allowed("finance_ops_coordinator", "start_ar_exception_triage")[0]
    assert is_tool_allowed("finance_ops_coordinator", "ingest_ar_feed")[0]
    assert is_tool_allowed("payments_agent", "start_ar_exception_triage")[0] is False
