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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from finance_ops.copilot.seed import (  # noqa: E402
    SPIKE_A_WALKTHROUGH,
    SPIKE_DIR,
    load_spike_a,
)

# Back-compat for `from scripts.load_spike_a import load`
load = load_spike_a


def _read_csv(name: str) -> list[dict[str, str]]:
    path = SPIKE_DIR / name
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


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

    def _ensure_payments_column(column: str, bq_type: str = "STRING") -> None:
        """Add a column if missing (live tables may predate bq_schema.sql)."""
        try:
            client.query(
                f"ALTER TABLE `{project}.{dataset}.payments` "
                f"ADD COLUMN IF NOT EXISTS {column} {bq_type}"
            ).result()
        except Exception:  # noqa: BLE001
            try:
                client.query(
                    f"ALTER TABLE `{project}.{dataset}.payments` "
                    f"ADD COLUMN {column} {bq_type}"
                ).result()
            except Exception:
                pass  # column may already exist

    # Live BQ payments may lack columns added later in bq_schema.sql
    _ensure_payments_column("matched_invoice_id")
    _ensure_payments_column("received_at")

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

    merge_notes: list[str] = []

    def _delete_ids(table: str, id_col: str, ids: list[str]) -> bool:
        """DELETE by id; return False if streaming buffer blocks (caller skips re-insert)."""
        if not ids:
            return True
        id_list = ", ".join(f"'{i}'" for i in ids)
        try:
            client.query(
                f"DELETE FROM `{project}.{dataset}.{table}` WHERE {id_col} IN ({id_list})"
            ).result()
            return True
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "streaming buffer" in msg.lower():
                merge_notes.append(
                    f"{table}: DELETE skipped (streaming buffer); keeping existing rows"
                )
                return False
            raise

    def _existing_ids(table: str, id_col: str, ids: list[str]) -> set[str]:
        if not ids:
            return set()
        id_list = ", ".join(f"'{i}'" for i in ids)
        rows = client.query(
            f"SELECT {id_col} AS id FROM `{project}.{dataset}.{table}` "
            f"WHERE {id_col} IN ({id_list})"
        ).result()
        return {str(r["id"]) for r in rows}

    if merge:
        # Prefer delete+insert; if streaming buffer blocks DELETE, insert only missing ids
        pay_ids = [r["payment_id"] for r in pay_rows]
        inv_ids = [r["invoice_id"] for r in inv_rows]
        pay_cleared = _delete_ids("payments", "payment_id", pay_ids)
        inv_cleared = _delete_ids("invoices", "invoice_id", inv_ids)
        if not pay_cleared:
            existing = _existing_ids("payments", "payment_id", pay_ids)
            pay_rows = [r for r in pay_rows if r["payment_id"] not in existing]
        if not inv_cleared:
            existing = _existing_ids("invoices", "invoice_id", inv_ids)
            inv_rows = [r for r in inv_rows if r["invoice_id"] not in existing]

    errors_inv = (
        client.insert_rows_json(f"{project}.{dataset}.invoices", inv_rows) if inv_rows else []
    )
    errors_pay = (
        client.insert_rows_json(f"{project}.{dataset}.payments", pay_rows) if pay_rows else []
    )
    ok = not errors_inv and not errors_pay
    return {
        "status": "success" if ok else "error",
        "project": project,
        "dataset": dataset,
        "counts": {"payments": len(pay_rows), "invoices": len(inv_rows)},
        "errors": {"invoices": errors_inv, "payments": errors_pay},
        "merge_notes": merge_notes,
        "walkthrough": list(SPIKE_A_WALKTHROUGH),
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
