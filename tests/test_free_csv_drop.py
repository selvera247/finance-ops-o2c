"""Free visibility: two CSVs → suggestions report (no apply)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[1]
PAYMENTS = REPO / "data" / "ar_feed" / "erp_unmatched_payments.csv"
INVOICES = REPO / "data" / "ar_feed" / "erp_open_ar.csv"


def test_run_free_csv_drop_sample_files() -> None:
    from finance_ops.runtime.free_csv_drop import run_free_csv_drop

    report = run_free_csv_drop(
        payments_csv=PAYMENTS,
        invoices_csv=INVOICES,
        company_name="Demo Co",
    )
    assert report["status"] == "success"
    assert report["sku"] == "free.visibility"
    summary = report["summary"]
    assert summary["unmatched_payment_count"] == 3
    assert summary["open_invoice_count"] >= 3
    assert summary["suggested_match_count"] >= 1
    assert any(s["payment_id"] == "PAY-FEED-01" for s in report["suggestions"])
    assert "Free tier" in report["markdown"] or "free" in report["markdown"].lower()


def test_column_aliases() -> None:
    from finance_ops.runtime.free_csv_drop import parse_payments_csv, parse_invoices_csv

    pay_csv = (
        "Txn_Id,Account_Id,Payment_Amount,Memo\n"
        "P1,C1,100.00,INV-1 remittance\n"
    ).encode()
    inv_csv = (
        "Invoice,Customer,Open_Amount,Status,PO\n"
        "INV-1,C1,100.00,open,PO-9\n"
    ).encode()
    payments = parse_payments_csv(pay_csv)
    invoices = parse_invoices_csv(inv_csv)
    assert payments[0]["payment_id"] == "P1"
    assert invoices[0]["invoice_id"] == "INV-1"


def test_http_free_visibility_multipart() -> None:
    from finance_ops.serving import app

    client = TestClient(app)
    with PAYMENTS.open("rb") as pf, INVOICES.open("rb") as inf:
        res = client.post(
            "/v1/ar/free_visibility",
            files={
                "payments_csv": ("payments.csv", pf, "text/csv"),
                "invoices_csv": ("invoices.csv", inf, "text/csv"),
            },
            data={"company_name": "HTTP Demo", "top_n": "10"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert body["summary"]["company_name"] == "HTTP Demo"
    assert "markdown" in body
