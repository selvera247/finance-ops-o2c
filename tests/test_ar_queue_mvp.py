"""MVP architecture — ar_exceptions projection, cache, /v1/ar APIs."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finance_ops.runtime.cache import TtlLruCache
from finance_ops.runtime.hitl import ApprovalStore
from finance_ops.services.queue_service import (
    get_exception,
    list_exceptions,
    mark_resolved,
    queue_metrics,
    sync_from_warehouse,
)
from finance_ops.services.sku_catalog import list_skus
from finance_ops.tools.queue_tools import start_ar_exception_triage
from pipelines.batch.ingest import ingest_batch
from scripts.load_spike_a import load as load_spike_a
from scripts.load_spike_b import load as load_spike_b


@pytest.fixture()
def warehouse_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ApprovalStore:
    ingest_batch(run_id="mvp-arch-batch")
    load_spike_a(replace_customers=True)
    load_spike_b()
    store = ApprovalStore(root=tmp_path / "hitl")
    monkeypatch.setattr("finance_ops.runtime.hitl.DEFAULT_STORE", store)
    monkeypatch.setattr("finance_ops.runtime.exception_queue.DEFAULT_STORE", store)
    return store


def test_cache_ttl_and_prefix() -> None:
    c = TtlLruCache(max_entries=8)
    c.set("ar:metrics:v1", {"x": 1}, ttl_seconds=60)
    c.set("ar:exceptions:list:open", {"y": 2}, ttl_seconds=60)
    c.set("other", 3, ttl_seconds=60)
    assert c.get("ar:metrics:v1") == {"x": 1}
    assert c.invalidate_prefix("ar:") == 2
    assert c.get("ar:metrics:v1") is None
    assert c.get("other") == 3


def test_sync_list_metrics(warehouse_ready: ApprovalStore) -> None:
    sync = sync_from_warehouse()
    assert sync["status"] == "success"
    assert sync["synced_count"] >= 1

    listed = list_exceptions(status="open", limit=100)
    assert listed["count"] >= 1
    assert listed["exceptions"][0]["exception_id"].startswith("EXE-")

    eid = listed["exceptions"][0]["exception_id"]
    got = get_exception(eid)
    assert got["status"] == "success"

    metrics = queue_metrics(use_cache=False)
    assert metrics["projection"]["exception_count"] >= 1
    assert "legacy_metrics" in metrics


def test_resolve_meters_sku(warehouse_ready: ApprovalStore) -> None:
    from data_plane import repository as repo
    from finance_ops.runtime.ar_feed import ingest_erp_payment_csv, stage_sample_erp_feed

    stage_sample_erp_feed()
    ingest_erp_payment_csv()
    sync_from_warehouse(payment_ids=["PAY-FEED-01"])
    applied = repo.apply_payment_match("PAY-FEED-01", "INV-84219")
    assert applied.get("ok")
    resolved = mark_resolved(
        source_id="PAY-FEED-01", lane="cash_app", invoice_id="INV-84219"
    )
    assert resolved["status"] == "success"
    assert resolved["sku_code"] == "resolve.cash_app"
    got = get_exception(resolved["exception_id"])
    assert got["exception"]["status"] == "resolved"

    metrics = queue_metrics(use_cache=False)
    assert metrics["projection"]["billable_resolves"] >= 1


def test_triage_syncs_projection(warehouse_ready: ApprovalStore) -> None:
    out = start_ar_exception_triage(
        stage_sample=True, request_hitl=False, use_live_hubspot=False
    )
    assert out["status"] == "success"
    assert (out.get("exception_sync") or {}).get("synced_count", 0) >= 1
    assert out.get("queue_projection") is not None


def test_http_ar_apis(warehouse_ready: ApprovalStore) -> None:
    from finance_ops.serving import app

    client = TestClient(app)
    sync = client.post("/v1/ar/exceptions/sync")
    assert sync.status_code == 200
    assert sync.json()["synced_count"] >= 1

    listed = client.get("/v1/ar/exceptions", params={"status": "open", "limit": 20})
    assert listed.status_code == 200
    body = listed.json()
    assert body["count"] >= 1
    eid = body["exceptions"][0]["exception_id"]

    one = client.get(f"/v1/ar/exceptions/{eid}")
    assert one.status_code == 200

    missing = client.get("/v1/ar/exceptions/EXE-missing")
    assert missing.status_code == 404

    metrics = client.get("/v1/ar/metrics")
    assert metrics.status_code == 200
    assert "projection" in metrics.json()

    skus = client.get("/v1/ar/skus")
    assert skus.status_code == 200
    codes = {s["code"] for s in skus.json()["skus"]}
    assert "free.visibility" in codes
    assert "resolve.cash_app" in codes


def test_sku_catalog() -> None:
    out = list_skus()
    assert out["status"] == "success"
    assert len(out["skus"]) >= 3
