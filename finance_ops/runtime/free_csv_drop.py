"""Drop two CSVs (unmatched payments + open AR) → free visibility report.

In-memory only by default — does not apply matches or require Cloud Run URL.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, BinaryIO, TextIO

from finance_ops.ar_queue.application.free_visibility import build_free_visibility_report

PAYMENT_ALIASES = {
    "payment_id": ("payment_id", "paymentid", "id", "txn_id", "transaction_id"),
    "customer_id": ("customer_id", "customerid", "cust_id", "account_id", "customer"),
    "amount": ("amount", "payment_amount", "amt", "value"),
    "currency": ("currency", "ccy", "curr"),
    "status": ("status", "payment_status"),
    "reference": ("reference", "ref", "memo", "description", "remittance"),
    "received_at": ("received_at", "payment_date", "date", "txn_date"),
}

INVOICE_ALIASES = {
    "invoice_id": ("invoice_id", "invoiceid", "inv_id", "invoice", "doc_number"),
    "customer_id": ("customer_id", "customerid", "cust_id", "account_id", "customer"),
    "amount": ("amount", "invoice_amount", "balance", "open_amount", "amt"),
    "currency": ("currency", "ccy", "curr"),
    "status": ("status", "invoice_status"),
    "due_date": ("due_date", "duedate", "due"),
    "issue_date": ("issue_date", "issuedate", "invoice_date", "date"),
    "po_number": ("po_number", "po", "purchase_order"),
    "customer_name": ("customer_name", "customername", "name"),
}


def _norm_header(name: str) -> str:
    return "".join(ch for ch in name.strip().lower().replace(" ", "_") if ch.isalnum() or ch == "_")


def _map_row(
    raw: dict[str, str],
    aliases: dict[str, tuple[str, ...]],
) -> dict[str, Any]:
    norm = {_norm_header(k): (v or "").strip() for k, v in raw.items() if k is not None}
    # also allow keys without underscores
    flat = {k.replace("_", ""): v for k, v in norm.items()}
    out: dict[str, Any] = {}
    for dest, names in aliases.items():
        val = ""
        for n in names:
            key = _norm_header(n)
            if key in norm and norm[key] != "":
                val = norm[key]
                break
            if key.replace("_", "") in flat and flat[key.replace("_", "")] != "":
                val = flat[key.replace("_", "")]
                break
        out[dest] = val
    return out


def _read_csv_rows(source: str | Path | TextIO | BinaryIO) -> list[dict[str, str]]:
    if isinstance(source, (str, Path)):
        path = Path(source)
        with path.open(newline="", encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh))
    if isinstance(source, (bytes, bytearray)):
        text = io.StringIO(source.decode("utf-8-sig"))
        return list(csv.DictReader(text))
    # file-like
    raw = source.read()
    if isinstance(raw, bytes):
        text = io.StringIO(raw.decode("utf-8-sig"))
    else:
        text = io.StringIO(raw)
    return list(csv.DictReader(text))


def parse_payments_csv(source: str | Path | TextIO | BinaryIO) -> list[dict[str, Any]]:
    rows = []
    for i, raw in enumerate(_read_csv_rows(source), start=2):
        mapped = _map_row(raw, PAYMENT_ALIASES)
        pid = str(mapped.get("payment_id") or "").strip().upper()
        if not pid:
            continue
        mapped["payment_id"] = pid
        mapped["customer_id"] = str(mapped.get("customer_id") or "").strip()
        mapped["status"] = (mapped.get("status") or "unmatched").lower() or "unmatched"
        mapped["currency"] = mapped.get("currency") or "USD"
        rows.append(mapped)
    return rows


def parse_invoices_csv(source: str | Path | TextIO | BinaryIO) -> list[dict[str, Any]]:
    rows = []
    for raw in _read_csv_rows(source):
        mapped = _map_row(raw, INVOICE_ALIASES)
        iid = str(mapped.get("invoice_id") or "").strip().upper()
        if not iid:
            continue
        mapped["invoice_id"] = iid
        mapped["customer_id"] = str(mapped.get("customer_id") or "").strip()
        mapped["status"] = (mapped.get("status") or "open").lower() or "open"
        mapped["currency"] = mapped.get("currency") or "USD"
        rows.append(mapped)
    return rows


def run_free_csv_drop(
    *,
    payments_csv: str | Path | TextIO | BinaryIO,
    invoices_csv: str | Path | TextIO | BinaryIO,
    company_name: str | None = None,
    top_n: int = 15,
) -> dict[str, Any]:
    """Parse two CSVs and build a free.visibility report (no apply)."""
    payments = parse_payments_csv(payments_csv)
    invoices = parse_invoices_csv(invoices_csv)
    if not payments:
        return {
            "status": "error",
            "error": "no_valid_payments",
            "hint": "Need payment_id, customer_id, amount columns",
            "needs_review": True,
        }
    if not invoices:
        return {
            "status": "error",
            "error": "no_valid_invoices",
            "hint": "Need invoice_id, customer_id, amount columns",
            "needs_review": True,
        }
    report = build_free_visibility_report(
        payments,
        invoices,
        company_name=company_name,
        top_n=top_n,
    )
    report["inputs"] = {
        "payment_rows": len(payments),
        "invoice_rows": len(invoices),
    }
    return report
