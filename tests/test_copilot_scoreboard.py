"""Copilot eval scoreboard — citation / harmful-error / abstain checkers + Spike A."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.copilot.checkers import (
    check_case,
    check_citation_validity,
    check_harmful_error,
    check_insufficient_calibration,
    summarize_scoreboard,
)
from evals.copilot.gold import load_gold_cases
from finance_ops.copilot import service as copilot
from pipelines.batch.ingest import ingest_batch
from scripts.load_spike_a import load as load_spike_a


@pytest.fixture()
def spike_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPILOT_MODE", "workbench")
    monkeypatch.setenv("COPILOT_EMAIL_EVIDENCE", "0")
    monkeypatch.setenv("FINANCE_OPS_DEMO_APPLY", "0")
    monkeypatch.setenv("COPILOT_FORCE_DETERMINISTIC", "1")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.delenv("FINANCE_OPS_API_TOKEN", raising=False)
    monkeypatch.delenv("FINANCE_OPS_LOCK_WRITES", raising=False)
    monkeypatch.setattr("finance_ops.copilot.store.REPO_ROOT", tmp_path)
    ingest_batch(run_id="copilot-scoreboard-batch")
    load_spike_a(replace_customers=True)
    from data_plane.warehouse import db

    db.init_schema()
    db.execute("DELETE FROM ar_exceptions WHERE lane = 'cash_app'")
    sync = copilot.ensure_queue(sync=True, force=True)
    assert sync.get("synced_count", 0) >= 1


def test_gold_loader_has_spike_cases() -> None:
    gold = load_gold_cases()
    assert gold.version.startswith("copilot-gold")
    ids = {c.id for c in gold.cases}
    assert "spike-a-pay-1001-exact" in ids
    assert "spike-a-pay-3001-orphan" in ids
    assert gold.targets["citation_validity"] >= 0.95


def test_citation_checker_requires_evidence_ids() -> None:
    gold = load_gold_cases().cases[0]
    hyp = {
        "insufficient_data": False,
        "confidence_band": "high",
        "lines": [{"invoice_id": "INV-84219", "amount": 1842.5}],
        "citation_map": [
            {"source_id": "MISSING", "source_type": "invoice", "claim": "x"},
        ],
    }
    ok, notes = check_citation_validity(
        hypothesis=hyp,
        evidence={"items": [{"source_id": "INV-84219", "source_type": "invoice"}]},
        gold=gold,
    )
    assert ok is False
    assert notes


def test_harmful_error_wrong_invoice() -> None:
    gold = next(c for c in load_gold_cases().cases if c.id == "spike-a-pay-1001-exact")
    hyp = {
        "insufficient_data": False,
        "confidence_band": "high",
        "lines": [{"invoice_id": "INV-WRONG", "amount": 1842.5}],
    }
    harmful, notes = check_harmful_error(hypothesis=hyp, gold=gold)
    assert harmful is True
    assert notes


def test_abstain_calibration() -> None:
    gold = next(c for c in load_gold_cases().cases if c.id == "spike-a-pay-3001-orphan")
    ok, _ = check_insufficient_calibration(
        hypothesis={
            "insufficient_data": True,
            "confidence_band": "insufficient",
            "lines": [],
        },
        gold=gold,
    )
    assert ok is True
    bad, _ = check_insufficient_calibration(
        hypothesis={
            "insufficient_data": False,
            "confidence_band": "high",
            "lines": [{"invoice_id": "INV-X", "amount": 1}],
        },
        gold=gold,
    )
    assert bad is False


def test_scoreboard_against_spike_a(spike_ready: None) -> None:
    gold_set = load_gold_cases()
    results = []
    for gold in gold_set.cases:
        case_id = copilot.case_id_for_payment(gold.payment_id)
        inv = copilot.investigate(case_id, actor="test-scoreboard")
        assert inv["status"] == "success", gold.payment_id
        results.append(
            check_case(
                gold,
                hypothesis=inv["hypothesis"],
                evidence=inv["evidence"],
            )
        )
    board = summarize_scoreboard(gold_set, results)
    assert board.case_count == len(gold_set.cases)
    assert board.citation_validity >= 0.95
    assert board.harmful_error_rate <= 0.02
    assert board.insufficient_calibration >= 0.85
    # Full pass preferred; keep assertion informative
    failed = [c for c in board.cases if not c.passed]
    assert not failed, [(c.case_id, c.notes) for c in failed]


def test_audit_persists_discovery_minimum(spike_ready: None) -> None:
    from finance_ops.copilot.types import Decision, DecisionRequest

    case_id = copilot.case_id_for_payment("PAY-1001")
    inv = copilot.investigate(case_id, actor="audit-test")
    assert inv["hypothesis"]["citation_map"]
    out = copilot.decide(
        case_id,
        DecisionRequest(decision=Decision.accept, actor="audit-test"),
    )
    assert out["status"] == "success"
    audit = copilot.get_audit(case_id)
    assert audit["raw_hypothesis"]
    assert audit["hypothesis"]
    assert audit["citation_map"]
    assert audit["decision_actor"] == "audit-test"
    assert audit["decision_at"]
    assert audit["confidence_band"]
    dec_events = [e for e in audit["audit"] if e.get("event") == "decision"]
    assert dec_events
    detail = dec_events[-1]["detail"]
    for key in (
        "case_id",
        "citation_map",
        "raw_hypothesis",
        "edited_hypothesis",
        "decision",
        "actor",
        "confidence_band",
    ):
        assert key in detail, key
