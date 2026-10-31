"""Free-tier reads stay open; mutating routes require write token when locked."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    from finance_ops.serving import app

    return TestClient(app)


def test_free_reads_open_without_token(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/v1/ar/skus").status_code == 200
    assert client.get("/v1/ar/metrics").status_code == 200
    assert client.get("/v1/ar/exceptions").status_code == 200
    assert client.get("/v1/ar_exception_queue").status_code == 200
    suggest = client.post("/v1/suggest_payment_match", json={"payment_id": "PAY-1001"})
    assert suggest.status_code == 200


def test_writes_open_locally_without_lock(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FINANCE_OPS_API_TOKEN", raising=False)
    monkeypatch.delenv("FINANCE_OPS_GOVERNANCE_TOKEN", raising=False)
    monkeypatch.delenv("FINANCE_OPS_LOCK_WRITES", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    # Sync may 200 or depend on warehouse; auth must not block.
    res = client.post("/v1/ar/exceptions/sync")
    assert res.status_code != 401
    assert res.status_code != 503


def test_cloud_run_without_token_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FINANCE_OPS_API_TOKEN", raising=False)
    monkeypatch.delenv("FINANCE_OPS_GOVERNANCE_TOKEN", raising=False)
    monkeypatch.setenv("K_SERVICE", "finance-ops")
    res = client.post(
        "/v1/request_cash_app_approval",
        json={"payment_id": "PAY-1001"},
    )
    assert res.status_code == 503
    assert "write auth not configured" in res.json()["detail"]


def test_lock_writes_requires_bearer(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FINANCE_OPS_API_TOKEN", "pilot-secret-token")
    monkeypatch.delenv("K_SERVICE", raising=False)

    denied = client.post(
        "/v1/request_cash_app_approval",
        json={"payment_id": "PAY-1001"},
    )
    assert denied.status_code == 401

    wrong = client.post(
        "/v1/request_cash_app_approval",
        json={"payment_id": "PAY-1001"},
        headers={"Authorization": "Bearer nope"},
    )
    assert wrong.status_code == 401

    # Auth accepted (not 401/503); body may be not_found for a fake approval id.
    ok = client.post(
        "/v1/decide_approval",
        json={"approval_id": "APPR-missing", "decision": "rejected"},
        headers={"Authorization": "Bearer pilot-secret-token"},
    )
    assert ok.status_code == 200

    ok_header = client.post(
        "/v1/request_approval",
        json={
            "kind": "write_off",
            "amount": 1.0,
            "summary": "auth smoke",
        },
        headers={"X-API-Token": "pilot-secret-token"},
    )
    assert ok_header.status_code == 200
    assert ok_header.status_code not in {401, 503}


def test_health_reports_auth(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FINANCE_OPS_API_TOKEN", "x")
    body = client.get("/health").json()
    assert body["auth"]["writes_locked"] is True
    assert body["auth"]["token_configured"] is True
    assert body["auth"]["free_tier"] == "visibility"
