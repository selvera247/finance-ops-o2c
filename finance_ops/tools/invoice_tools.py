from __future__ import annotations

from typing import Any

from data_plane import repository as repo
from finance_ops.lib.evidence import record_evidence


def lookup_invoice(invoice_id: str) -> dict[str, Any]:
    """Look up a single invoice by invoice_id (e.g. INV-1001)."""
    invoice_id = invoice_id.strip().upper()
    match = repo.get_invoice(invoice_id)
    if not match:
        result = {
            "status": "not_found",
            "invoice_id": invoice_id,
            "needs_review": True,
        }
    else:
        # Normalize potential datetime values from DuckDB
        result = {
            "status": "success",
            "invoice": {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in match.items()},
            "needs_review": False,
        }

    evidence = record_evidence(
        agent="invoice_agent",
        action="lookup_invoice",
        inputs={"invoice_id": invoice_id},
        outputs=result,
        sources=[repo.source_label()] if match else [],
    )
    result["evidence"] = evidence
    return result


def list_open_invoices(customer_id: str | None = None) -> dict[str, Any]:
    """List open or past_due invoices, optionally filtered by customer_id."""
    rows = repo.list_invoices(customer_id=customer_id, open_only=True)
    clean = [
        {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in row.items()}
        for row in rows
    ]
    result = {
        "status": "success",
        "count": len(clean),
        "invoices": clean,
        "needs_review": False,
    }
    evidence = record_evidence(
        agent="invoice_agent",
        action="list_open_invoices",
        inputs={"customer_id": customer_id},
        outputs={"count": len(clean)},
        sources=[repo.source_label()],
    )
    result["evidence"] = evidence
    return result


def aging_summary(customer_id: str | None = None) -> dict[str, Any]:
    """Summarize AR aging buckets for open/past_due invoices."""
    rows = repo.list_invoices(customer_id=customer_id, open_only=True)
    buckets: dict[str, float] = {}
    for row in rows:
        bucket = str(row["aging_bucket"])
        buckets[bucket] = buckets.get(bucket, 0.0) + float(row["amount"])
    result = {
        "status": "success",
        "customer_id": customer_id,
        "total_open": sum(buckets.values()),
        "buckets": buckets,
        "invoice_count": len(rows),
        "needs_review": False,
    }
    evidence = record_evidence(
        agent="invoice_agent",
        action="aging_summary",
        inputs={"customer_id": customer_id},
        outputs=result,
        sources=[repo.source_label()],
    )
    result["evidence"] = evidence
    return result
