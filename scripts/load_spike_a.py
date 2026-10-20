#!/usr/bin/env python3
"""Load Spike A cash-app CSVs into the DuckDB warehouse (merge/upsert).

Does not wipe demo fixtures — inserts/replaces by primary key so you can
run suggest_payment_match on PAY-1001 / PAY-2001 / PAY-3001 alongside
existing CUST-ACME data.

Usage:
  PYTHONPATH=. python scripts/load_spike_a.py
  PYTHONPATH=. python scripts/load_spike_a.py --replace-customers   # delete C-* rows first
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SPIKE_DIR = ROOT / "data" / "spike_a"


def _now():
    return datetime.now(timezone.utc)


def _read_csv(name: str) -> list[dict[str, str]]:
    path = SPIKE_DIR / name
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load(*, replace_customers: bool = False) -> dict:
    from data_plane.warehouse import db

    db.init_schema()
    payments = _read_csv("payments.csv")
    invoices = _read_csv("invoices.csv")
    now = _now()
    customer_ids = sorted({r["customer_id"] for r in payments} | {r["customer_id"] for r in invoices})

    con = db.connect()
    try:
        if replace_customers and customer_ids:
            placeholders = ",".join("?" * len(customer_ids))
            con.execute(
                f"DELETE FROM payments WHERE customer_id IN ({placeholders})",
                customer_ids,
            )
            con.execute(
                f"DELETE FROM invoices WHERE customer_id IN ({placeholders})",
                customer_ids,
            )

        for row in invoices:
            inv_id = row["invoice_id"].strip()
            cust = row["customer_id"].strip()
            amount = float(row["amount"])
            status = row["status"].strip()
            po = (row.get("po_number") or "").strip() or None
            currency = (row.get("currency") or "USD").strip()
            # Fill warehouse-required columns with demo-safe defaults
            con.execute("DELETE FROM invoices WHERE invoice_id = ?", [inv_id])
            con.execute(
                "INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                [
                    inv_id,
                    cust,
                    f"Customer {cust}",
                    f"CTR-{cust}",
                    amount,
                    currency,
                    "2026-09-01",
                    "2026-09-30",
                    status,
                    "1-30" if status == "open" else "31-60",
                    po,
                    now,
                ],
            )

        for row in payments:
            pay_id = row["payment_id"].strip()
            cust = row["customer_id"].strip()
            amount = float(row["amount"])
            currency = (row.get("currency") or "USD").strip()
            status = row["status"].strip()
            reference = row.get("reference") or ""
            received = (row.get("received_at") or row.get("payment_date") or "2026-10-01").strip()
            con.execute("DELETE FROM payments WHERE payment_id = ?", [pay_id])
            con.execute(
                "INSERT INTO payments VALUES (?,?,?,?,?,?,?,?,?,?)",
                [
                    pay_id,
                    cust,
                    amount,
                    currency,
                    received,  # payment_date
                    "ACH",  # method default for bank/lockbox-shaped feed
                    reference,
                    None,  # matched_invoice_id
                    status,
                    now,
                ],
            )

        return {
            "status": "success",
            "spike_dir": str(SPIKE_DIR),
            "customers": customer_ids,
            "counts": {"payments": len(payments), "invoices": len(invoices)},
            "walkthrough": ["PAY-1001", "PAY-2001", "PAY-3001"],
        }
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replace-customers",
        action="store_true",
        help="Delete existing warehouse rows for Spike A customer_ids before load",
    )
    args = parser.parse_args()
    result = load(replace_customers=args.replace_customers)
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
