"""Cold warehouse Sync must auto-seed Spike A so cash_app queue populates."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finance_ops.copilot import service as copilot
from finance_ops.serving import app


@pytest.fixture()
def empty_warehouse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    duck = tmp_path / "cold.duckdb"
    # DUCKDB_PATH is resolved at import — patch the live config value.
    monkeypatch.setattr("data_plane.config.DUCKDB_PATH", duck)
    monkeypatch.setenv("FINANCE_OPS_DUCKDB", str(duck))
    monkeypatch.setenv("FINANCE_OPS_DATA_MODE", "warehouse")
    monkeypatch.setenv("COPILOT_MODE", "workbench")
    monkeypatch.setenv("COPILOT_AUTO_SEED", "1")
    monkeypatch.setenv("COPILOT_SYNC_MIN_INTERVAL_SEC", "0")
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.delenv("FINANCE_OPS_API_TOKEN", raising=False)
    monkeypatch.delenv("FINANCE_OPS_LOCK_WRITES", raising=False)
    monkeypatch.setattr("finance_ops.copilot.store.REPO_ROOT", tmp_path)
    monkeypatch.setattr(copilot, "_LAST_SYNC_MONO", 0.0)
    assert not duck.exists()
    return duck


def test_ensure_queue_seeds_empty_warehouse(empty_warehouse: Path) -> None:
    sync = copilot.ensure_queue(sync=True, force=True)
    assert sync.get("status") == "success"
    assert sync.get("seed", {}).get("status") == "success"
    assert sync.get("seed", {}).get("seeded") is True
    assert int(sync.get("payment_count") or 0) >= 1
    assert int(sync.get("synced_count") or 0) >= 1
    assert empty_warehouse.exists()

    queue = copilot.list_queue(lane="cash_app", sync_first=False, limit=50)
    assert queue["count"] >= 1
    assert any(str(c["case_id"]).startswith("EXE-cash_app-") for c in queue["cases"])
    assert any(c.get("payment_id") == "PAY-1001" for c in queue["cases"])


def test_auto_seed_can_be_disabled(
    empty_warehouse: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COPILOT_AUTO_SEED", "0")
    monkeypatch.setattr(copilot, "_LAST_SYNC_MONO", 0.0)
    sync = copilot.ensure_queue(sync=True, force=True)
    assert int(sync.get("payment_count") or 0) == 0
    assert sync.get("seed", {}).get("status") == "disabled"
    assert sync.get("hint")
    queue = copilot.list_queue(lane="cash_app", sync_first=False, limit=50)
    assert queue["count"] == 0


def test_queue_api_sync_populates_cash_app(empty_warehouse: Path) -> None:
    client = TestClient(app)
    res = client.get("/v1/copilot/queue", params={"sync": "true", "lane": "cash_app"})
    assert res.status_code == 200
    body = res.json()
    assert body.get("count", 0) >= 1
    assert any(str(c["case_id"]).startswith("EXE-cash_app-") for c in body["cases"])
    sync_meta = body.get("sync") or {}
    assert int(sync_meta.get("payment_count") or 0) >= 1
    assert sync_meta.get("seed", {}).get("status") == "success"
