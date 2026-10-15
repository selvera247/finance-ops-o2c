from __future__ import annotations

from typing import Any

from finance_ops.lib.evidence import record_evidence
from finance_ops.lib.fixtures import invoices


def lookup_invoice(invoice_id: str) -> dict[str, Any]:
    """Look up a single invoice by invoice_id (e.g. INV-1001)."""
    invoice_id = invoice_id.strip().upper()
    match = next((i for i in invoices() if i["invoice_id"] == invoice_id), None)
    if not match:
        result = {
            "status": "not_found",
            "invoice_id": invoice_id,
            "needs_review": True,
        }
    else:
        result = {"status": "success", "invoice": match, "needs_review": False}

    evidence = record_evidence(
        agent="invoice_agent",
        action="lookup_invoice",
        inputs={"invoice_id": invoice_id},
        outputs=result,
        sources=["fixture:invoices.json"] if match else [],
    )
    result["evidence"] = evidence
    return result


def list_open_invoices(customer_id: str | None = None) -> dict[str, Any]:
    """List open or past_due invoices, optionally filtered by customer_id."""
    rows = [
        i
        for i in invoices()
        if i["status"] in {"open", "past_due"}
        and (customer_id is None or i["customer_id"] == customer_id)
    ]
    result = {
        "status": "success",
        "count": len(rows),
        "invoices": rows,
        "needs_review": False,
    }
    evidence = record_evidence(
        agent="invoice_agent",
        action="list_open_invoices",
        inputs={"customer_id": customer_id},
        outputs={"count": len(rows)},
        sources=["fixture:invoices.json"],
    )
    result["evidence"] = evidence
    return result


def aging_summary(customer_id: str | None = None) -> dict[str, Any]:
    """Summarize AR aging buckets for open/past_due invoices."""
    rows = [
        i
        for i in invoices()
        if i["status"] in {"open", "past_due"}
        and (customer_id is None or i["customer_id"] == customer_id)
    ]
    buckets: dict[str, float] = {}
    for row in rows:
        buckets[row["aging_bucket"]] = buckets.get(row["aging_bucket"], 0.0) + float(
            row["amount"]
        )
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
        sources=["fixture:invoices.json"],
    )
    result["evidence"] = evidence
    return result
