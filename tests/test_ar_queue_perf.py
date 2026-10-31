"""Performance-oriented correctness for batch scoring, PK lookups, cache-before-ensure."""

from __future__ import annotations

from pathlib import Path

import pytest

from finance_ops.runtime.cache import DEFAULT_CACHE
from finance_ops.runtime.hitl import ApprovalStore
from finance_ops.services.queue_service import (
    list_exceptions,
    queue_metrics,
    sync_from_warehouse,
    upsert_exceptions_batch,
)
from finance_ops.tools.payment_tools import score_payment_match, score_payments_batch
from pipelines.batch.ingest import ingest_batch
from scripts.load_spike_a import load as load_spike_a
from scripts.load_spike_b import load as load_spike_b


@pytest.fixture()
def warehouse_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ApprovalStore:
    ingest_batch(run_id="perf-test-batch")
    load_spike_a(replace_customers=True)
    load_spike_b()
    store = ApprovalStore(root=tmp_path / "hitl")
    monkeypatch.setattr("finance_ops.runtime.hitl.DEFAULT_STORE", store)
    monkeypatch.setattr("finance_ops.runtime.exception_queue.DEFAULT_STORE", store)
    DEFAULT_CACHE.clear()
    return store


def test_batch_score_matches_single(warehouse_ready: ApprovalStore) -> None:
    from data_plane import repository as repo

    payments = repo.list_payments(unmatched_only=True)
    assert payments, "expected unmatched fixture payments"
    batch = score_payments_batch(payments)
    for pay in payments:
        pid = str(pay["payment_id"]).upper()
        single = score_payment_match(pid)
        assert batch[pid]["recommendation"] == single["recommendation"]
        assert [c["invoice_id"] for c in batch[pid]["candidates"]] == [
            c["invoice_id"] for c in single["candidates"]
        ]
        assert [c["score"] for c in batch[pid]["candidates"]] == [
            c["score"] for c in single["candidates"]
        ]


def test_pk_lookups(warehouse_ready: ApprovalStore) -> None:
    from data_plane import repository as repo

    pay = repo.list_payments()[0]
    inv = repo.list_invoices()[0]
    assert repo.get_payment(str(pay["payment_id"]).lower()) is not None
    assert repo.get_invoice(str(inv["invoice_id"]).lower()) is not None
    assert repo.get_payment("PAY-DOES-NOT-EXIST") is None
    assert repo.get_invoice("INV-DOES-NOT-EXIST") is None


def test_batch_upsert_and_cache_hit(warehouse_ready: ApprovalStore) -> None:
    sync = sync_from_warehouse(include_portal=True, include_hubspot_gaps=True)
    assert sync["synced_count"] >= 1

    cold = list_exceptions(status="open", limit=50)
    assert cold["count"] >= 1
    hits_before = DEFAULT_CACHE.stats().get("hits", 0)
    warm = list_exceptions(status="open", limit=50)
    assert warm == cold
    assert DEFAULT_CACHE.stats().get("hits", 0) >= hits_before + 1

    m_cold = queue_metrics(use_cache=True)
    hits_m = DEFAULT_CACHE.stats().get("hits", 0)
    m_warm = queue_metrics(use_cache=True)
    assert m_warm["projection"] == m_cold["projection"]
    assert DEFAULT_CACHE.stats().get("hits", 0) >= hits_m + 1


def test_upsert_batch_empty() -> None:
    assert upsert_exceptions_batch([]) == []


def test_triage_batch_path(warehouse_ready: ApprovalStore) -> None:
    from finance_ops.runtime.ar_feed import triage_unmatched_payments

    out = triage_unmatched_payments()
    assert out["status"] == "success"
    assert out["payment_count"] >= 1
    assert len(out["suggestions"]) >= 1
    missing = triage_unmatched_payments(payment_ids=["PAY-NOPE"])
    assert missing["suggestions"][0]["status"] == "not_found"
