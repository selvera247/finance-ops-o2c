"""Copilot performance-oriented correctness: slim queue, evidence cache, overlay batching."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from finance_ops.ar_queue.adapters.ttl_cache import DEFAULT_QUEUE_CACHE
from finance_ops.ar_queue.adapters.warehouse_exceptions import DEFAULT_EXCEPTION_STORE
from finance_ops.ar_queue.domain.statuses import OPEN_STATUSES
from finance_ops.copilot import service as copilot
from finance_ops.copilot import store as case_store
from finance_ops.copilot.evidence_cache import cache_stats, invalidate_evidence
from pipelines.batch.ingest import ingest_batch
from scripts.load_spike_a import load as load_spike_a


def _reopen_fixture_case(case_id: str) -> None:
    """Prior suites may leave PAY-1001 terminal; sync preserves closed_rejected."""
    store = DEFAULT_EXCEPTION_STORE
    store.ensure_schema()
    row = store.fetch_by_id(case_id)
    assert row is not None, f"missing exception row for {case_id}"
    if str(row.get("status") or "") in OPEN_STATUSES:
        return
    now = datetime.now(timezone.utc)
    store.replace_row(
        {**row, "status": "open", "resolved_at": None},
        opened_at=row.get("opened_at") or now,
        now=now,
    )
    DEFAULT_QUEUE_CACHE.invalidate_queue()


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
    case_id = copilot.case_id_for_payment("PAY-1001")
    _reopen_fixture_case(case_id)
    return case_id


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


def test_queue_summary_uses_overlay_meta_cache(
    spike_ready: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Second summary list should hit process overlay meta (no full re-parse)."""
    case_id = spike_ready
    copilot.investigate(case_id, actor="perf")
    # Use a wide limit so ranking cannot drop the fixture case off the page.
    first = copilot.list_queue(limit=200, detail="summary")
    assert first["status"] == "success"
    assert any(c["case_id"] == case_id for c in first["cases"])

    opens: list[str] = []
    real_load = case_store.load_overlay

    def _counting_load(cid: str) -> dict:
        opens.append(cid)
        return real_load(cid)

    monkeypatch.setattr(case_store, "load_overlay", _counting_load)
    second = copilot.list_queue(limit=200, detail="summary")
    assert second["status"] == "success"
    # Meta cache should satisfy summary path — no disk load for known cases.
    assert case_id not in opens
    row = next(c for c in second["cases"] if c["case_id"] == case_id)
    assert "insufficient_data" in row
    assert row.get("hypothesis") is None


def test_queue_rank_columns_omit_payload(spike_ready: str) -> None:
    from finance_ops.ar_queue.application.queries import list_exceptions

    ranked = list_exceptions(status="open", lane="cash_app", limit=20, columns="rank")
    assert ranked["status"] == "success"
    assert ranked["count"] >= 1
    for row in ranked["exceptions"]:
        assert "exception_id" in row
        assert "amount" in row
        assert "match_score" in row
        assert "payload" not in row or row.get("payload") in (None, {}, [])
        assert "payload_json" not in row


def test_evidence_audit_once_per_invalidate(spike_ready: str) -> None:
    case_id = spike_ready
    invalidate_evidence(case_id)
    first = copilot.get_evidence(case_id, actor="perf")
    assert first.get("cache") == "miss"
    # Force rebuild without invalidate — should still skip second evidence_retrieved.
    from finance_ops.copilot import evidence_cache as ecache

    ecache._CACHE.clear()
    second = copilot.get_evidence(case_id, actor="perf")
    assert second.get("cache") == "miss"
    overlay = case_store.load_overlay(case_id)
    events = [e.get("event") for e in (overlay.get("audit") or [])]
    assert events.count("evidence_retrieved") == 1


def test_audit_limit_returns_tail(spike_ready: str) -> None:
    case_id = spike_ready
    copilot.investigate(case_id, actor="perf")
    for _ in range(3):
        copilot.get_evidence(case_id, actor="perf")
    limited = copilot.get_audit(case_id, limit=1)
    assert limited["status"] == "success"
    assert len(limited["audit"]) == 1
    assert limited["audit_total"] >= 1
    assert limited["audit_limit"] == 1
    full = copilot.get_audit(case_id, limit=None)
    assert len(full["audit"]) == full["audit_total"]


def test_decide_inline_hypothesis_single_write(
    spike_ready: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from finance_ops.copilot.types import (
        Decision,
        DecisionRequest,
        HypothesisUpdate,
        MatchLine,
    )

    case_id = spike_ready
    inv = copilot.investigate(case_id, actor="perf")
    hyp = inv.get("hypothesis") or {}
    lines = hyp.get("lines") or []
    if not lines:
        pytest.skip("no lines to edit inline")

    writes: list[str] = []
    real_save = case_store.save_overlay

    def _counting_save(cid: str, data: dict) -> dict:
        writes.append(cid)
        return real_save(cid, data)

    monkeypatch.setattr(case_store, "save_overlay", _counting_save)
    out = copilot.decide(
        case_id,
        DecisionRequest(
            decision=Decision.edit_ready_to_apply,
            actor="perf",
            hypothesis=HypothesisUpdate(
                lines=[MatchLine.model_validate(lines[0])],
                raw_notes="perf inline",
            ),
        ),
    )
    assert out["status"] == "success"
    assert writes == [case_id]


def test_digest_detail_lean(spike_ready: str) -> None:
    queue = copilot.list_queue(limit=10, detail="digest")
    assert queue["detail"] == "digest"
    assert queue["count"] >= 1
    for case in queue["cases"]:
        assert case.get("guidance") is None
        assert case.get("payload") == {}
        hyp = case.get("hypothesis")
        assert hyp is None or isinstance(hyp, dict)
        if isinstance(hyp, dict):
            assert "lines" in hyp
            assert "confidence_band" in hyp or hyp.get("confidence_band") is None


def test_queue_list_latency_smoke(spike_ready: str) -> None:
    """Capture summary vs full wall time for the optimization report."""
    import time

    # Warm schema / overlays.
    copilot.list_queue(limit=50, detail="summary")
    t0 = time.perf_counter()
    for _ in range(5):
        copilot.list_queue(limit=50, detail="summary")
    summary_ms = (time.perf_counter() - t0) / 5 * 1000
    t1 = time.perf_counter()
    for _ in range(5):
        copilot.list_queue(limit=50, detail="full")
    full_ms = (time.perf_counter() - t1) / 5 * 1000
    # Summary should not be slower than full (allow tiny noise).
    assert summary_ms <= full_ms * 1.5 + 5.0
    # Expose numbers in assertion message for report capture.
    assert summary_ms >= 0, f"summary={summary_ms:.2f}ms full={full_ms:.2f}ms"
    print(f"PERF queue_list summary_ms={summary_ms:.2f} full_ms={full_ms:.2f}")


def test_slim_audit_detail_drops_hyp_blobs() -> None:
    slim = case_store.slim_audit_detail(
        {
            "confidence_band": "high",
            "raw_hypothesis": {
                "confidence_band": "high",
                "lines": [{"invoice_id": "INV-1"}],
            },
            "edited_hypothesis": {"lines": []},
            "citation_map": [{"source_id": "pay-1", "label": "x"}],
        }
    )
    assert "raw_hypothesis" not in slim
    assert "edited_hypothesis" not in slim
    assert slim.get("hyp_confidence_band") == "high"
    assert slim.get("hyp_line_count") == 1
    assert slim.get("citation_map") == ["pay-1"]
