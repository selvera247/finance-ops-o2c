"""Demo warehouse seed for Copilot Sync / Refresh.

Cloud Run containers start with an empty ephemeral DuckDB. Calling
``sync_from_warehouse`` first runs ``ensure_schema()``, which creates that
empty file and disables the fixtures fallback — Sync then reports success
with ``payment_count=0`` and the cash_app workbench queue stays empty.

## Demo packs (``COPILOT_DEMO_SEED_PACK``)

| Pack | Source | Marker payments | Notes |
| --- | --- | --- | --- |
| ``base`` | ``data/*.json`` via ``ingest_batch`` (same as ``POST /v1/bootstrap``) | ``PAY-9002``, ``PAY-9003`` | Core demo warehouse (CUST-ACME / NORTH / GLOBEX) |
| ``spike_a`` | ``data/spike_a/*.csv`` | ``PAY-1001``, ``PAY-2001``, ``PAY-3001`` | Cash-app walkthrough + eval gold |
| ``base+spike_a`` (default) | both, base first then Spike A merge | all of the above | Matches prior workbench screenshots (900x + 100x/200x/400x) |

Spike B (``data/spike_b``) is **portal remittance** (``CLM-B*``, lane ``portal_remittance``) — not the cash_app queue.

Set ``COPILOT_AUTO_SEED=0`` to disable Sync-time seeding entirely.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from typing import Any

from data_plane import config as data_config
from finance_ops.copilot.config import _truthy

SPIKE_DIR = data_config.DATA_DIR / "spike_a"
SPIKE_A_WALKTHROUGH = ("PAY-1001", "PAY-2001", "PAY-3001")
BASE_DEMO_MARKERS = ("PAY-9002", "PAY-9003")
SPIKE_A_MARKERS = ("PAY-1001", "PAY-2001")

# Default pack restores the richer combined workbench dataset.
DEFAULT_DEMO_SEED_PACK = "base+spike_a"


def _falsy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"0", "false", "no", "off"}


def auto_seed_enabled() -> bool:
    """Auto-seed on Sync. Default on; set COPILOT_AUTO_SEED=0 to disable."""
    if _falsy("COPILOT_AUTO_SEED"):
        return False
    if _truthy("COPILOT_AUTO_SEED"):
        return True
    return True


def demo_seed_pack() -> str:
    """Which fixture pack(s) Sync should materialize when the warehouse is incomplete."""
    raw = os.getenv("COPILOT_DEMO_SEED_PACK", DEFAULT_DEMO_SEED_PACK).strip().lower()
    if raw in {"base", "bootstrap", "warehouse"}:
        return "base"
    if raw in {"spike_a", "spike-a", "spikea"}:
        return "spike_a"
    if raw in {"base+spike_a", "base+spike-a", "full", "demo", ""}:
        return "base+spike_a"
    return DEFAULT_DEMO_SEED_PACK


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


def warehouse_has_payment(payment_id: str) -> bool:
    if not data_config.DUCKDB_PATH.exists():
        return False
    present = warehouse_payments_present((payment_id,))
    return payment_id.strip().upper() in present


def warehouse_payments_present(payment_ids: tuple[str, ...] | list[str]) -> set[str]:
    """Batch marker probe — one DuckDB connect for many payment ids."""
    ids = [p.strip().upper() for p in payment_ids if p and str(p).strip()]
    if not ids or not data_config.DUCKDB_PATH.exists():
        return set()
    from data_plane.warehouse import db

    db.init_schema()
    found: set[str] = set()
    # Chunk to stay under parameter limits on large marker sets.
    for i in range(0, len(ids), 200):
        chunk = ids[i : i + 200]
        placeholders = ",".join("?" * len(chunk))
        rows = db.query_dicts(
            f"SELECT UPPER(payment_id) AS pid FROM payments "
            f"WHERE UPPER(payment_id) IN ({placeholders})",
            chunk,
        )
        for row in rows:
            pid = row.get("pid")
            if pid:
                found.add(str(pid).upper())
    return found


def _missing_markers(markers: tuple[str, ...]) -> list[str]:
    present = warehouse_payments_present(markers)
    return [pid for pid in markers if pid.strip().upper() not in present]


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
        db.close_connection(con)


def load_base_warehouse(*, run_id: str = "copilot-demo-seed") -> dict[str, Any]:
    """Load committed ``data/*.json`` demo warehouse (PAY-900x / CUST-*)."""
    from pipelines.batch.ingest import ingest_batch

    return ingest_batch(run_id=run_id)


def ensure_demo_payments(*, force: bool = False) -> dict[str, Any]:
    """Seed the configured demo pack when the warehouse is empty or incomplete.

    Does **not** silently replace a complete warehouse with Spike A alone.
    If base markers are missing (e.g. prior Spike-A-only seed), reloads
    ``base`` then merges Spike A so PAY-9002/9003 return alongside Spike A.

    ``COPILOT_AUTO_SEED=0`` always disables seeding.
    """
    if not auto_seed_enabled():
        return {"status": "disabled", "reason": "COPILOT_AUTO_SEED=0"}

    pack = demo_seed_pack()
    want_base = pack in {"base", "base+spike_a"}
    want_spike = pack in {"spike_a", "base+spike_a"}

    missing_base = _missing_markers(BASE_DEMO_MARKERS) if want_base else []
    missing_spike = _missing_markers(SPIKE_A_MARKERS) if want_spike else []

    if not force and not missing_base and not missing_spike:
        return {
            "status": "skipped",
            "reason": "demo_pack_present",
            "pack": pack,
            "payment_count": warehouse_unmatched_payment_count(),
        }

    steps: list[dict[str, Any]] = []
    seeded = False

    # ingest_batch wipes payments/invoices — if base is missing/forced, reload
    # Spike A afterward whenever the pack includes it.
    if want_base and (force or missing_base):
        base = load_base_warehouse()
        steps.append({"step": "base", **base})
        if base.get("status") != "success":
            return {
                "status": "error",
                "error": "base_seed_failed",
                "pack": pack,
                "steps": steps,
            }
        seeded = True
        if want_spike:
            spike = load_spike_a(replace_customers=False)
            steps.append({"step": "spike_a", **spike})
            if spike.get("status") != "success":
                return {
                    "status": "error",
                    "error": "spike_a_seed_failed",
                    "pack": pack,
                    "steps": steps,
                }
    elif want_spike and (force or missing_spike):
        spike = load_spike_a(replace_customers=False)
        steps.append({"step": "spike_a", **spike})
        if spike.get("status") != "success":
            return {
                "status": "error",
                "error": "spike_a_seed_failed",
                "pack": pack,
                "steps": steps,
            }
        seeded = True

    return {
        "status": "success",
        "seeded": seeded or force or bool(steps),
        "pack": pack,
        "steps": steps,
        "payment_count": warehouse_unmatched_payment_count(),
        "markers": {
            "base": list(BASE_DEMO_MARKERS),
            "spike_a": list(SPIKE_A_MARKERS),
        },
    }


# Back-compat alias used by earlier Sync fix / callers.
def ensure_spike_a_payments(*, force: bool = False) -> dict[str, Any]:
    return ensure_demo_payments(force=force)
