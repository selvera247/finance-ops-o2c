"""Demo warehouse seed for Copilot (Spike A cash-app fixtures).

Cloud Run containers start with an empty ephemeral DuckDB. Calling
``sync_from_warehouse`` first runs ``ensure_schema()``, which creates that
empty file and disables the fixtures fallback — Sync then reports success
with ``payment_count=0`` and the cash_app workbench queue stays empty.

This module loads ``data/spike_a/*.csv`` into DuckDB so Sync/Refresh can
materialize EXE-cash_app-* cases without a manual bootstrap step.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_plane import config as data_config

SPIKE_DIR = data_config.DATA_DIR / "spike_a"
SPIKE_A_WALKTHROUGH = ("PAY-1001", "PAY-2001", "PAY-3001")


def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _falsy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"0", "false", "no", "off"}


def auto_seed_enabled() -> bool:
    """Spike A auto-seed on Sync. Default on; set COPILOT_AUTO_SEED=0 to disable."""
    if _falsy("COPILOT_AUTO_SEED"):
        return False
    if _truthy("COPILOT_AUTO_SEED"):
        return True
    return True


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_csv(name: str) -> list[dict[str, str]]:
    path = SPIKE_DIR / name
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def spike_a_available() -> bool:
    return (SPIKE_DIR / "payments.csv").is_file() and (SPIKE_DIR / "invoices.csv").is_file()


def warehouse_unmatched_payment_count() -> int:
    """Count unmatched/partial payments in DuckDB only (ignores fixture fallback)."""
    if not data_config.DUCKDB_PATH.exists():
        return 0
    from data_plane.warehouse import db

    db.init_schema()
    rows = db.query_dicts(
        "SELECT COUNT(*) AS n FROM payments WHERE status IN ('unmatched', 'partial')"
    )
    return int((rows[0] or {}).get("n") or 0) if rows else 0


def load_spike_a(*, replace_customers: bool = False) -> dict[str, Any]:
    """Load Spike A cash-app CSVs into the DuckDB warehouse (merge/upsert)."""
    if not spike_a_available():
        return {
            "status": "error",
            "error": "spike_a_csv_missing",
            "spike_dir": str(SPIKE_DIR),
        }

    from data_plane.warehouse import db

    db.init_schema()
    payments = _read_csv("payments.csv")
    invoices = _read_csv("invoices.csv")
    now = _now()
    customer_ids = sorted(
        {r["customer_id"] for r in payments} | {r["customer_id"] for r in invoices}
    )

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
            received = (
                row.get("received_at") or row.get("payment_date") or "2026-10-01"
            ).strip()
            con.execute("DELETE FROM payments WHERE payment_id = ?", [pay_id])
            con.execute(
                "INSERT INTO payments VALUES (?,?,?,?,?,?,?,?,?,?)",
                [
                    pay_id,
                    cust,
                    amount,
                    currency,
                    received,
                    "ACH",
                    reference,
                    None,
                    status,
                    now,
                ],
            )

        return {
            "status": "success",
            "spike_dir": str(SPIKE_DIR),
            "customers": customer_ids,
            "counts": {"payments": len(payments), "invoices": len(invoices)},
            "walkthrough": list(SPIKE_A_WALKTHROUGH),
        }
    finally:
        con.close()


def ensure_spike_a_payments(*, force: bool = False) -> dict[str, Any]:
    """Seed Spike A when the warehouse has no unmatched payments.

    ``force`` re-loads even when payments already exist. ``COPILOT_AUTO_SEED=0``
    always disables seeding (force cannot override the kill switch).

    Returns a status dict: skipped | success | error | disabled.
    """
    if not auto_seed_enabled():
        return {"status": "disabled", "reason": "COPILOT_AUTO_SEED=0"}

    if not force:
        existing = warehouse_unmatched_payment_count()
        if existing > 0:
            return {
                "status": "skipped",
                "reason": "payments_present",
                "payment_count": existing,
            }

    loaded = load_spike_a(replace_customers=False)
    if loaded.get("status") != "success":
        return loaded
    return {
        **loaded,
        "seeded": True,
        "payment_count": warehouse_unmatched_payment_count(),
    }
