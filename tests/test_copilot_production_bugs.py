"""Regression tests for Copilot production failure modes (siblings of #8–#10)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from data_plane import repository as repo
from finance_ops.ar_queue.adapters.warehouse_exceptions import WarehouseExceptionStore
from finance_ops.ar_queue.domain.matching import score_against_invoices
from finance_ops.copilot import service as copilot
from finance_ops.copilot import store as case_store
from finance_ops.copilot.email_evidence.acl import actor_may_access_customer, load_actor_acl
from finance_ops.copilot.evidence_cache import (
    cache_evidence_pack,
    get_cached_evidence,
    invalidate_evidence,
)
from finance_ops.copilot.types import (
    Decision,
    DecisionRequest,
    HypothesisUpdate,
    MatchLine,
)
from finance_ops.serving import app
from pipelines.batch.ingest import ingest_batch
from scripts.load_spike_a import load as load_spike_a


@pytest.fixture()
def prod_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    duck = tmp_path / "prod.duckdb"
    monkeypatch.setattr("data_plane.config.DUCKDB_PATH", duck)
    monkeypatch.setenv("FINANCE_OPS_DUCKDB", str(duck))
    monkeypatch.setenv("FINANCE_OPS_DATA_MODE", "warehouse")
    monkeypatch.setenv("COPILOT_MODE", "workbench")
    monkeypatch.setenv("COPILOT_AUTO_SEED", "1")
    monkeypatch.setenv("COPILOT_DEMO_SEED_PACK", "base+spike_a")
    monkeypatch.setenv("COPILOT_SYNC_MIN_INTERVAL_SEC", "0")
    monkeypatch.setenv("COPILOT_EVIDENCE_CACHE_TTL_SEC", "45")
    monkeypatch.setenv("FINANCE_OPS_DEMO_APPLY", "0")
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.delenv("FINANCE_OPS_API_TOKEN", raising=False)
    monkeypatch.delenv("FINANCE_OPS_LOCK_WRITES", raising=False)
    monkeypatch.setattr("finance_ops.copilot.store.REPO_ROOT", tmp_path)
    monkeypatch.setattr(copilot, "_LAST_SYNC_MONO", 0.0)
    invalidate_evidence()
    load_actor_acl(force=True)
    return tmp_path


@pytest.fixture()
def seeded(prod_env: Path) -> str:
    ingest_batch(run_id="prod-bug-batch")
    load_spike_a(replace_customers=True)
    sync = copilot.ensure_queue(sync=True, force=True)
    assert sync.get("synced_count", 0) >= 1
    return copilot.case_id_for_payment("PAY-1001")


def test_replace_row_atomic_under_concurrent_reads(seeded: str) -> None:
    """DELETE+INSERT must not expose a missing PK to parallel GET /cases."""
    store = WarehouseExceptionStore()
    row = store.fetch_by_id(seeded)
    assert row is not None
    client = TestClient(app)
    errors: list[str] = []

    def _upsert() -> None:
        try:
            for i in range(20):
                mutated = {**row, "match_score": float(i)}
                store.replace_row(
                    mutated,
                    opened_at=row.get("opened_at") or datetime.now(timezone.utc),
                    now=datetime.now(timezone.utc),
                )
        except Exception as exc:  # noqa: BLE001 — surface any race failure
            errors.append(f"upsert:{exc}")

    def _read() -> None:
        for _ in range(40):
            res = client.get(f"/v1/copilot/cases/{seeded}")
            if res.status_code != 200:
                errors.append(f"get:{res.status_code}")
                continue
            body = res.json()
            if body.get("status") != "success":
                errors.append(f"get_status:{body.get('status')}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(_upsert) for _ in range(2)] + [
            pool.submit(_read) for _ in range(6)
        ]
        for fut in as_completed(futs):
            fut.result()

    assert not errors, errors[:8]
    assert store.fetch_by_id(seeded) is not None


def test_overlay_rmw_preserves_hypothesis_under_parallel_evidence(
    seeded: str, prod_env: Path
) -> None:
    """Investigate persist must not be clobbered by GET evidence audit append."""
    case_id = seeded
    lost = []

    def _investigate() -> None:
        out = copilot.investigate(case_id, actor="test")
        if out.get("status") != "success":
            lost.append(f"investigate:{out.get('status')}")

    def _evidence() -> None:
        out = copilot.get_evidence(case_id, actor="test")
        if out.get("status") != "success":
            lost.append(f"evidence:{out.get('status')}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = []
        for _ in range(6):
            futs.append(pool.submit(_investigate))
            futs.append(pool.submit(_evidence))
        for fut in as_completed(futs):
            fut.result()

    overlay = case_store.load_overlay(case_id)
    assert overlay.get("hypothesis"), "hypothesis lost to overlay race"
    events = [e.get("event") for e in (overlay.get("audit") or [])]
    assert "investigate" in events
    assert "evidence_retrieved" in events
    assert not lost, lost


def test_workbench_actor_in_acl(prod_env: Path) -> None:
    load_actor_acl(force=True)
    assert actor_may_access_customer("workbench", "C-1042") is True
    assert actor_may_access_customer("workbench", "CUST-ACME") is True


def test_apply_payment_match_reports_miss_when_no_row(prod_env: Path) -> None:
    from data_plane.warehouse import db

    db.init_schema()
    out = repo.apply_payment_match("PAY-DOES-NOT-EXIST", "INV-MISS")
    assert out["ok"] is False
    assert out["error"] == "payment_not_found"


def test_apply_payment_match_verifies_update(seeded: str) -> None:
    pay = repo.get_payment("PAY-1001")
    assert pay is not None
    # Use a known open invoice for that customer from Spike A walkthrough.
    invs = repo.list_invoices(customer_id=str(pay["customer_id"]))
    open_inv = next(
        (i for i in invs if str(i.get("status")) == "open"),
        invs[0] if invs else None,
    )
    assert open_inv is not None
    out = repo.apply_payment_match("PAY-1001", str(open_inv["invoice_id"]))
    assert out["ok"] is True
    verified = repo.get_payment("PAY-1001")
    assert verified is not None
    assert str(verified.get("status")).lower() == "matched"


def test_matching_casefold_and_token_boundary() -> None:
    payment = {
        "payment_id": "PAY-X",
        "customer_id": "C1",
        "amount": 100.0,
        "reference": "please apply inv-10 and po-99",
        "currency": "USD",
    }
    invoices = [
        {
            "invoice_id": "inv-1",  # must NOT match inside inv-10
            "po_number": "po-1",
            "amount": 50.0,
            "status": "open",
        },
        {
            "invoice_id": "INV-10",
            "po_number": "PO-99",
            "amount": 100.0,
            "status": "open",
        },
    ]
    out = score_against_invoices(payment, invoices)
    assert out["recommendation"] == "INV-10"
    ids = {c["invoice_id"] for c in out["candidates"]}
    assert "inv-1" not in ids
    assert "INV-10" in ids


def test_decide_invalidates_evidence_cache(seeded: str, monkeypatch: pytest.MonkeyPatch) -> None:
    case_id = seeded
    cache_evidence_pack(
        case_id,
        actor="test",
        pack={"case_id": case_id, "items": [{"source_id": "stale"}], "email_enabled": False},
    )
    assert get_cached_evidence(case_id, actor="test") is not None
    copilot.decide(
        case_id,
        DecisionRequest(
            decision=Decision.need_info,
            actor="test",
            reason_code="need_info_remittance",
        ),
    )
    assert get_cached_evidence(case_id, actor="test") is None


def test_multi_line_demo_apply_refused(
    seeded: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FINANCE_OPS_DEMO_APPLY", "1")
    case_id = seeded
    inv = copilot.investigate(case_id, actor="test")
    assert inv["status"] == "success"
    copilot.update_hypothesis(
        case_id,
        HypothesisUpdate(
            lines=[
                MatchLine(invoice_id="INV-84219", amount=100.0),
                MatchLine(invoice_id="INV-99999", amount=50.0),
            ],
            confidence_band="medium",
        ),
        actor="test",
    )
    out = copilot.decide(
        case_id,
        DecisionRequest(decision=Decision.edit_ready_to_apply, actor="test"),
    )
    assert out["status"] == "success"
    assert out["warehouse_applied"] is False
    wr = (out.get("guidance") or {}).get("warehouse_apply_result") or {}
    assert wr.get("error") == "multi_line_demo_apply_unsupported"


def test_blank_api_token_env_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    from finance_ops.serving import _write_token_expected, write_auth_status

    monkeypatch.setenv("FINANCE_OPS_API_TOKEN", "   ")
    monkeypatch.delenv("FINANCE_OPS_GOVERNANCE_TOKEN", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    assert _write_token_expected() == ""
    assert write_auth_status()["token_configured"] is False
