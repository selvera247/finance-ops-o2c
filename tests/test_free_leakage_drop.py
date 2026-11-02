"""Free sold-vs-invoiced leakage report tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[1]
CLOSED_WON = REPO / "data" / "ar_feed" / "crm_closed_won.csv"
INVOICES = REPO / "data" / "ar_feed" / "erp_open_ar.csv"


def test_run_free_leakage_sample() -> None:
    from finance_ops.runtime.free_leakage_drop import run_free_leakage_drop

    report = run_free_leakage_drop(
        closed_won_csv=CLOSED_WON,
        invoices_csv=INVOICES,
        company_name="Leak Demo",
    )
    assert report["status"] == "success"
    assert report["lane"] == "sold_vs_invoiced"
    summary = report["summary"]
    assert summary["gap_customer_count"] >= 1
    assert summary["positive_leakage_usd"] > 0
    assert any(g["customer_id"] == "C-1042" for g in report["gaps"])
    assert "leakage" in report["markdown"].lower()


def test_sold_without_invoices_flag() -> None:
    from finance_ops.ar_queue.application.free_leakage import build_free_leakage_report

    report = build_free_leakage_report(
        [{"customer_id": "C-X", "sold": 10000, "company_name": "X"}],
        [{"invoice_id": "INV-OTHER", "customer_id": "C-Y", "amount": 100, "status": "open"}],
    )
    gap = next(g for g in report["gaps"] if g["customer_id"] == "C-X")
    assert "sold_without_invoices" in gap["gaps"]


def test_http_free_leakage() -> None:
    from finance_ops.serving import app

    client = TestClient(app)
    with CLOSED_WON.open("rb") as cf, INVOICES.open("rb") as inf:
        res = client.post(
            "/v1/ar/free_leakage",
            files={
                "closed_won_csv": ("won.csv", cf, "text/csv"),
                "invoices_csv": ("inv.csv", inf, "text/csv"),
            },
            data={"company_name": "HTTP Leak"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert body["summary"]["company_name"] == "HTTP Leak"


def test_leakage_self_serve_page() -> None:
    from finance_ops.serving import app

    client = TestClient(app)
    res = client.get("/leakage")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    html = res.text
    assert "Finance Ops" in html
    assert 'id="leak-form"' in html
    assert "/v1/ar/free_leakage" in html
    assert 'name="closed_won_csv"' in html
    assert 'name="invoices_csv"' in html

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json().get("self_serve", {}).get("leakage") == "/leakage"
