"""Pure payment ↔ invoice match scoring (no I/O, no breaker, no evidence)."""

from __future__ import annotations

from typing import Any

from finance_ops.ar_queue.domain.serialize import clean_row


def score_against_invoices(
    payment: dict[str, Any],
    invoices: list[dict[str, Any]],
) -> dict[str, Any]:
    """Score one payment against a preloaded invoice list (CPU-only)."""
    candidates = []
    pay_amt = float(payment.get("amount") or 0)
    ref = (payment.get("reference") or "").upper()
    for inv in invoices:
        score, reasons = 0.0, []
        if inv["invoice_id"] in ref:
            score += 0.7
            reasons.append("invoice_id_in_reference")
        if inv.get("po_number") and str(inv["po_number"]) in ref:
            score += 0.4
            reasons.append("po_in_reference")
        inv_amt = float(inv["amount"] or 0)
        amount_delta = abs(inv_amt - pay_amt)
        if amount_delta <= max(1.0, inv_amt * 0.005):
            score += 0.5
            reasons.append("amount_within_tolerance")
        elif pay_amt < inv_amt:
            score += 0.2
            reasons.append("possible_partial")
        if score > 0:
            candidates.append(
                {
                    "invoice_id": inv["invoice_id"],
                    "score": round(score, 2),
                    "reasons": reasons,
                    "invoice_amount": inv["amount"],
                    "invoice_status": inv["status"],
                }
            )
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return {
        "status": "success",
        "payment": clean_row(payment),
        "candidates": candidates[:5],
        "needs_review": True,
        "recommendation": candidates[0]["invoice_id"] if candidates else None,
    }


def score_payments_batch_cpu(
    payments: list[dict[str, Any]],
    invoices_by_customer: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """Batch-score payments given a pre-grouped invoice map (CPU-only)."""
    out: dict[str, dict[str, Any]] = {}
    for payment in payments:
        pid = str(payment.get("payment_id") or "").strip().upper()
        if not pid:
            continue
        cust = str(payment.get("customer_id") or "")
        out[pid] = score_against_invoices(
            payment, invoices_by_customer.get(cust) or []
        )
    return out
