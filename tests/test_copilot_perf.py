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
    """detail=full keeps nested blobs; summary nulls them (independent of rank page)."""
    from finance_ops.ar_queue.application.queries import get_exception
    from finance_ops.copilot import store as overlay_store
    from finance_ops.copilot.service import _row_to_case, _row_to_case_summary

    case_id = spike_ready
    inv = copilot.investigate(case_id, actor="perf")
    assert inv["status"] == "success"
    row = get_exception(case_id)["exception"]
    overlay = overlay_store.load_overlay(case_id)
    fat = _row_to_case(row, overlay).model_dump()
    slim = _row_to_case_summary(row, overlay)
    assert fat.get("hypothesis") is not None
    assert fat["hypothesis"]["confidence_band"]
    assert slim.get("hypothesis") is None
    assert slim.get("summary") is None
    assert slim.get("guidance") is None
    assert slim.get("payload") == {}
    # HTTP list path still accepts detail=full without error.
    listed = copilot.list_queue(limit=200, detail="full")
    assert listed["detail"] == "full"
    assert listed["count"] >= 1


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


def test_decide_single_overlay_write(
    spike_ready: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Accept path should persist guidance + decision + audit in one overlay write."""
    from finance_ops.copilot.types import Decision, DecisionRequest

    case_id = spike_ready
    inv = copilot.investigate(case_id, actor="perf")
    assert inv["status"] == "success"
    hyp = inv.get("hypothesis") or {}
    if hyp.get("insufficient_data") or not hyp.get("lines"):
        pytest.skip("fixture case abstains; cannot exercise accept overlay write")

    writes: list[str] = []
    real_save = case_store.save_overlay

    def _counting_save(cid: str, data: dict) -> dict:
        writes.append(cid)
        return real_save(cid, data)

    monkeypatch.setattr(case_store, "save_overlay", _counting_save)
    out = copilot.decide(
        case_id,
        DecisionRequest(decision=Decision.accept, actor="perf"),
    )
    assert out["status"] == "success"
    assert writes == [case_id]
    overlay = case_store.load_overlay(case_id)
    assert overlay.get("guidance")
    assert overlay.get("last_decision") == "accept"
    assert any(e.get("event") == "decision" for e in overlay.get("audit") or [])
