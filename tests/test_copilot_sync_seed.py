"""Cold warehouse Sync must auto-seed the demo pack (base + Spike A)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finance_ops.copilot import service as copilot
from finance_ops.copilot import seed as demo_seed
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
    monkeypatch.setenv("COPILOT_DEMO_SEED_PACK", "base+spike_a")
    monkeypatch.setenv("COPILOT_SYNC_MIN_INTERVAL_SEC", "0")
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.delenv("FINANCE_OPS_API_TOKEN", raising=False)
    monkeypatch.delenv("FINANCE_OPS_LOCK_WRITES", raising=False)
    monkeypatch.setattr("finance_ops.copilot.store.REPO_ROOT", tmp_path)
    monkeypatch.setattr(copilot, "_LAST_SYNC_MONO", 0.0)
    assert not duck.exists()
    return duck


def _payment_ids(queue: dict) -> set[str]:
    return {str(c.get("payment_id") or "") for c in queue.get("cases") or []}


def test_ensure_queue_seeds_base_and_spike_a(empty_warehouse: Path) -> None:
    sync = copilot.ensure_queue(sync=True, force=True)
    assert sync.get("status") == "success"
    seed = sync.get("seed") or {}
    assert seed.get("status") == "success"
    assert seed.get("seeded") is True
    assert seed.get("pack") == "base+spike_a"
    assert int(sync.get("payment_count") or 0) >= 1
    assert empty_warehouse.exists()

    queue = copilot.list_queue(lane="cash_app", sync_first=False, limit=50)
    ids = _payment_ids(queue)
    # Prior workbench dataset: bootstrap PAY-900x + Spike A PAY-1001…
    assert "PAY-9002" in ids
    assert "PAY-9003" in ids
    assert "PAY-1001" in ids


def test_spike_a_only_warehouse_upgrades_to_include_base(
    empty_warehouse: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate the first Sync fix that seeded Spike A alone.
    demo_seed.load_spike_a(replace_customers=False)
    assert demo_seed.warehouse_has_payment("PAY-1001")
    assert not demo_seed.warehouse_has_payment("PAY-9002")

    monkeypatch.setattr(copilot, "_LAST_SYNC_MONO", 0.0)
    sync = copilot.ensure_queue(sync=True, force=True)
    assert sync.get("seed", {}).get("status") == "success"
    queue = copilot.list_queue(lane="cash_app", sync_first=False, limit=50)
    ids = _payment_ids(queue)
    assert "PAY-9002" in ids
    assert "PAY-9003" in ids
    assert "PAY-1001" in ids


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
    ids = _payment_ids(body)
    assert "PAY-9003" in ids
    assert "PAY-1001" in ids
    sync_meta = body.get("sync") or {}
    assert sync_meta.get("seed", {}).get("pack") == "base+spike_a"
