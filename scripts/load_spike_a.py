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


def load_bigquery(*, merge: bool = True) -> dict:
    """Upsert Spike A rows into BigQuery finance_ops dataset."""
    import os

    from data_plane.config import bigquery_dataset, gcp_project

    project = gcp_project() or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        return {"status": "error", "error": "GOOGLE_CLOUD_PROJECT required"}

    from google.cloud import bigquery

    dataset = bigquery_dataset()
    client = bigquery.Client(project=project)

    # Ensure matched_invoice_id exists (ignore if already present)
    try:
        client.query(
            f"ALTER TABLE `{project}.{dataset}.payments` "
            "ADD COLUMN IF NOT EXISTS matched_invoice_id STRING"
        ).result()
    except Exception as exc:  # noqa: BLE001
        # Older BQ without IF NOT EXISTS — try bare ADD once
        try:
            client.query(
                f"ALTER TABLE `{project}.{dataset}.payments` "
                "ADD COLUMN matched_invoice_id STRING"
            ).result()
        except Exception:
            pass  # column may already exist
        _ = exc

    payments = _read_csv("payments.csv")
    invoices = _read_csv("invoices.csv")

    inv_rows = []
    for row in invoices:
        status = row["status"].strip()
        inv_rows.append(
            {
                "invoice_id": row["invoice_id"].strip(),
                "customer_id": row["customer_id"].strip(),
                "amount": float(row["amount"]),
                "currency": (row.get("currency") or "USD").strip(),
                "status": status,
                "aging_bucket": "1-30" if status == "open" else "31-60",
                "due_date": "2026-09-30",
                "po_number": (row.get("po_number") or "").strip() or None,
            }
        )

    pay_rows = []
    for row in payments:
        pay_rows.append(
            {
                "payment_id": row["payment_id"].strip(),
                "customer_id": row["customer_id"].strip(),
                "amount": float(row["amount"]),
                "currency": (row.get("currency") or "USD").strip(),
                "status": row["status"].strip(),
                "reference": row.get("reference") or "",
                "received_at": (row.get("received_at") or "").strip(),
                "matched_invoice_id": None,
            }
        )

    if merge:
        # Delete spike payment/invoice ids then insert (idempotent reload)
        pay_ids = [r["payment_id"] for r in pay_rows]
        inv_ids = [r["invoice_id"] for r in inv_rows]
        if pay_ids:
            id_list = ", ".join(f"'{i}'" for i in pay_ids)
            client.query(
                f"DELETE FROM `{project}.{dataset}.payments` WHERE payment_id IN ({id_list})"
            ).result()
        if inv_ids:
            id_list = ", ".join(f"'{i}'" for i in inv_ids)
            client.query(
                f"DELETE FROM `{project}.{dataset}.invoices` WHERE invoice_id IN ({id_list})"
            ).result()

    errors_inv = client.insert_rows_json(f"{project}.{dataset}.invoices", inv_rows)
    errors_pay = client.insert_rows_json(f"{project}.{dataset}.payments", pay_rows)
    ok = not errors_inv and not errors_pay
    return {
        "status": "success" if ok else "error",
        "project": project,
        "dataset": dataset,
        "counts": {"payments": len(pay_rows), "invoices": len(inv_rows)},
        "errors": {"invoices": errors_inv, "payments": errors_pay},
        "walkthrough": ["PAY-1001", "PAY-2001", "PAY-3001"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replace-customers",
        action="store_true",
        help="Delete existing warehouse rows for Spike A customer_ids before load",
    )
    parser.add_argument(
        "--bigquery",
        action="store_true",
        help="Also (or only with --bigquery-only) load into BigQuery",
    )
    parser.add_argument(
        "--bigquery-only",
        action="store_true",
        help="Skip DuckDB; load Spike A into BigQuery only",
    )
    args = parser.parse_args()
    out: dict = {}
    if not args.bigquery_only:
        out["warehouse"] = load(replace_customers=args.replace_customers)
    if args.bigquery or args.bigquery_only:
        out["bigquery"] = load_bigquery(merge=True)
    print(json.dumps(out if len(out) > 1 else next(iter(out.values())), indent=2))
    warehouse_ok = out.get("warehouse", {}).get("status", "success") == "success"
    bq_ok = out.get("bigquery", {}).get("status", "success") == "success"
    if args.bigquery_only:
        return 0 if bq_ok else 1
    if args.bigquery:
        return 0 if warehouse_ok and bq_ok else 1
    return 0 if warehouse_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
