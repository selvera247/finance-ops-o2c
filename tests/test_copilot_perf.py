"""Copilot performance-oriented correctness: slim queue, evidence cache, overlay batching."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from finance_ops.copilot import service as copilot
from finance_ops.copilot import store as case_store
from finance_ops.copilot.evidence_cache import cache_stats, invalidate_evidence
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
    monkeypatch.setattr("finance_ops.copilot.store.REPO_ROOT", tmp_path)
    invalidate_evidence()
    ingest_batch(run_id="copilot-perf-batch")
    load_spike_a(replace_customers=True)
    sync = copilot.ensure_queue(sync=True, force=True)
    assert sync.get("synced_count", 0) >= 1
    return copilot.case_id_for_payment("PAY-1001")


def test_queue_summary_omits_heavy_blobs(spike_ready: str) -> None:
    queue = copilot.list_queue(limit=20, detail="summary")
    assert queue["status"] == "success"
    assert queue["detail"] == "summary"
    assert queue["count"] >= 1
    for case in queue["cases"]:
        assert case.get("hypothesis") is None
        assert case.get("summary") is None
        assert case.get("guidance") is None
        assert case.get("payload") == {}
        assert "case_id" in case
        assert "amount" in case
        assert "status" in case
        assert "confidence_band" in case
        assert "insufficient_data" in case


def test_queue_full_keeps_nested_after_investigate(spike_ready: str) -> None:
    case_id = spike_ready
    inv = copilot.investigate(case_id, actor="perf")
    assert inv["status"] == "success"
    fat = copilot.list_queue(limit=50, detail="full")
    found = next(c for c in fat["cases"] if c["case_id"] == case_id)
    assert found.get("hypothesis") is not None
    assert found["hypothesis"]["confidence_band"]


def test_evidence_cache_hit_skips_rebuild(spike_ready: str) -> None:
    case_id = spike_ready
    first = copilot.get_evidence(case_id, actor="perf")
    assert first["status"] == "success"
    assert first.get("cache") == "miss"
    assert cache_stats()["entries"] >= 1
    second = copilot.get_evidence(case_id, actor="perf")
    assert second["status"] == "success"
    assert second.get("cache") == "hit"
    assert second["evidence"]["case_id"] == first["evidence"]["case_id"]
    assert len(second["evidence"]["items"]) == len(first["evidence"]["items"])


def test_investigate_single_overlay_write(spike_ready: str) -> None:
    case_id = spike_ready
    path = case_store.case_path(case_id)
    if path.is_file():
        path.unlink()
    inv = copilot.investigate(case_id, actor="perf")
    assert inv["status"] == "success"
    assert path.is_file()
    raw = path.read_text(encoding="utf-8")
    # Compact JSON (no pretty indent) keeps overlay I/O smaller.
    assert "\n  \"hypothesis\"" not in raw
    data = json.loads(raw)
    assert data.get("hypothesis")
    assert data.get("summary")
    assert any(e.get("event") == "investigate" for e in data.get("audit") or [])
    cached = copilot.get_evidence(case_id, actor="perf")
    assert cached.get("cache") == "hit"


def test_sync_throttle(spike_ready: str, monkeypatch: pytest.MonkeyPatch) -> None:
    import finance_ops.copilot.service as svc

    monkeypatch.setenv("COPILOT_SYNC_MIN_INTERVAL_SEC", "60")
    monkeypatch.setattr(svc, "_LAST_SYNC_MONO", 0.0)
    first = svc.ensure_queue(sync=True)
    assert first.get("status") != "throttled"
    second = svc.ensure_queue(sync=True)
    assert second.get("status") == "throttled"
    forced = svc.ensure_queue(sync=True, force=True)
    assert forced.get("status") != "throttled"
