"""Drop closed-won + invoices CSVs → free sold-vs-invoiced leakage report."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, BinaryIO, TextIO

from finance_ops.ar_queue.application.free_leakage import build_free_leakage_report

CLOSED_WON_ALIASES = {
    "customer_id": (
        "customer_id",
        "customerid",
        "cust_id",
        "account_id",
        "company_customer_id",
        "erp_customer_id",
    ),
    "sold": ("sold", "amount", "deal_amount", "acv", "tcv", "closed_amount"),
    "company_name": ("company_name", "customer_name", "company", "account_name", "name"),
    "deal_id": ("deal_id", "dealid", "hs_deal_id", "opportunity_id", "id"),
}

INVOICE_ALIASES = {
    "invoice_id": ("invoice_id", "invoiceid", "inv_id", "invoice", "doc_number"),
    "customer_id": ("customer_id", "customerid", "cust_id", "account_id", "customer"),
    "amount": ("amount", "invoice_amount", "balance", "open_amount", "amt"),
    "status": ("status", "invoice_status"),
    "customer_name": ("customer_name", "customername", "name"),
}


def _norm_header(name: str) -> str:
    return "".join(
        ch for ch in name.strip().lower().replace(" ", "_") if ch.isalnum() or ch == "_"
    )


def _map_row(raw: dict[str, str], aliases: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    norm = {_norm_header(k): (v or "").strip() for k, v in raw.items() if k is not None}
    flat = {k.replace("_", ""): v for k, v in norm.items()}
    out: dict[str, Any] = {}
    for dest, names in aliases.items():
        val = ""
        for n in names:
            key = _norm_header(n)
            if key in norm and norm[key] != "":
                val = norm[key]
                break
            compact = key.replace("_", "")
            if compact in flat and flat[compact] != "":
                val = flat[compact]
                break
        out[dest] = val
    return out


def _read_csv_rows(source: str | Path | TextIO | BinaryIO | bytes) -> list[dict[str, str]]:
    if isinstance(source, (str, Path)):
        with Path(source).open(newline="", encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh))
    if isinstance(source, (bytes, bytearray)):
        return list(csv.DictReader(io.StringIO(source.decode("utf-8-sig"))))
    raw = source.read()
    if isinstance(raw, bytes):
        return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    return list(csv.DictReader(io.StringIO(raw)))


def parse_closed_won_csv(source: str | Path | TextIO | BinaryIO | bytes) -> list[dict[str, Any]]:
    rows = []
    for raw in _read_csv_rows(source):
        mapped = _map_row(raw, CLOSED_WON_ALIASES)
        cust = str(mapped.get("customer_id") or "").strip().upper()
        if not cust:
            continue
        mapped["customer_id"] = cust
        if mapped.get("deal_id"):
            mapped["deal_id"] = str(mapped["deal_id"]).strip()
        rows.append(mapped)
    return rows


def parse_invoices_csv(source: str | Path | TextIO | BinaryIO | bytes) -> list[dict[str, Any]]:
    rows = []
    for raw in _read_csv_rows(source):
        mapped = _map_row(raw, INVOICE_ALIASES)
        iid = str(mapped.get("invoice_id") or "").strip().upper()
        cust = str(mapped.get("customer_id") or "").strip().upper()
        if not iid or not cust:
            continue
        mapped["invoice_id"] = iid
        mapped["customer_id"] = cust
        mapped["status"] = (mapped.get("status") or "open").lower() or "open"
        rows.append(mapped)
    return rows


def run_free_leakage_drop(
    *,
    closed_won_csv: str | Path | TextIO | BinaryIO | bytes,
    invoices_csv: str | Path | TextIO | BinaryIO | bytes,
    company_name: str | None = None,
    top_n: int = 25,
) -> dict[str, Any]:
    closed_won = parse_closed_won_csv(closed_won_csv)
    invoices = parse_invoices_csv(invoices_csv)
    if not closed_won:
        return {
            "status": "error",
            "error": "no_valid_closed_won",
            "hint": "Need customer_id + sold/amount (CRM closed-won export)",
            "needs_review": True,
        }
    if not invoices:
        return {
            "status": "error",
            "error": "no_valid_invoices",
            "hint": "Need invoice_id, customer_id, amount",
            "needs_review": True,
        }
    report = build_free_leakage_report(
        closed_won,
        invoices,
        company_name=company_name,
        top_n=top_n,
    )
    report["inputs"] = {
        "closed_won_rows": len(closed_won),
        "invoice_rows": len(invoices),
    }
    return report
