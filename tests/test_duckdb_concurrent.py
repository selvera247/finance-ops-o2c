"""DuckDB file access must tolerate concurrent Copilot case/evidence/audit reads."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finance_ops.copilot import service as copilot
from finance_ops.serving import app


@pytest.fixture()
def seeded_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, str]:
    duck = tmp_path / "concurrent.duckdb"
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

    client = TestClient(app)
    q = client.get("/v1/copilot/queue?sync=true&lane=cash_app&detail=summary")
    assert q.status_code == 200
    cases = q.json().get("cases") or []
    assert cases, "expected seeded queue"
    case_id = str(cases[0]["case_id"])
    return client, case_id


def test_parallel_case_evidence_audit_no_500(seeded_client: tuple[TestClient, str]) -> None:
    client, case_id = seeded_client
    paths = [
        f"/v1/copilot/cases/{case_id}",
        f"/v1/copilot/cases/{case_id}/evidence?actor=workbench",
        f"/v1/copilot/cases/{case_id}/audit",
    ]

    def _get(path: str) -> tuple[str, int]:
        res = client.get(path)
        return path, res.status_code

    # Burst like the workbench openCase Promise.all (repeated for flake coverage).
    jobs: list[str] = []
    for _ in range(8):
        jobs.extend(paths)

    results: list[tuple[str, int]] = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = [pool.submit(_get, p) for p in jobs]
        for fut in as_completed(futs):
            results.append(fut.result())

    failures = [(p, s) for p, s in results if s != 200]
    assert not failures, f"expected all 200, got failures={failures[:6]}"
