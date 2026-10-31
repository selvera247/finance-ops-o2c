"""Pure portal extract classification (no I/O, no breaker, no evidence)."""

from __future__ import annotations

import re
from typing import Any

from finance_ops.ar_queue.domain.serialize import clean_row

SPIKE_B_WALKTHROUGH = ("CLM-B1001", "CLM-B2001", "CLM-B3001")
_INV_RE = re.compile(r"\bINV-[A-Z0-9]+\b", re.I)


def classify_portal_row(claim_id: str, row: dict[str, Any] | None) -> dict[str, Any]:
    """Classify a portal extract line for review routing."""
    claim_id = claim_id.strip().upper()
    if not row:
        return {
            "status": "not_found",
            "claim_id": claim_id,
            "hint": "Run python scripts/load_spike_b.py first",
            "needs_review": True,
        }

    status = str(row.get("status") or "").lower()
    desc = str(row.get("description") or "")
    amount = float(row.get("amount") or 0)
    invoice_mentions = _INV_RE.findall(desc)
    invoice_ids = sorted({m.upper() for m in invoice_mentions})

    if status == "denied":
        disposition = "escalate_appeal"
        kind = "portal_claim_denied"
    elif status == "pending":
        disposition = "watch_sla"
        kind = "portal_claim_pending"
    elif status == "paid" and not invoice_ids and "orphan" in desc.lower():
        disposition = "escalate_orphan"
        kind = "portal_orphan_cash"
    elif status == "paid" and invoice_ids:
        disposition = "accept_remittance"
        kind = "portal_remittance_match"
    elif status == "paid":
        disposition = "review_underpay_or_match"
        kind = "portal_remittance_review"
    else:
        disposition = "needs_review"
        kind = "portal_extract_review"

    return {
        "status": "success",
        "claim_id": claim_id,
        "extract": clean_row(row),
        "disposition": disposition,
        "hitl_kind": kind,
        "suggested_invoice_ids": invoice_ids,
        "amount": amount,
        "needs_review": disposition != "accept_remittance",
    }
