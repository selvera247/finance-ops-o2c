from __future__ import annotations

from typing import Any

from data_plane import repository as repo
from finance_ops.lib.evidence import record_evidence


def _clean(row: dict[str, Any]) -> dict[str, Any]:
    return {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in row.items()}


def lookup_payment(payment_id: str) -> dict[str, Any]:
    payment_id = payment_id.strip().upper()
    match = repo.get_payment(payment_id)
    result = (
        {"status": "not_found", "payment_id": payment_id, "needs_review": True}
        if not match
        else {"status": "success", "payment": _clean(match), "needs_review": False}
    )
    result["evidence"] = record_evidence(
        agent="payments_agent", action="lookup_payment",
        inputs={"payment_id": payment_id}, outputs=result,
        sources=[repo.source_label()] if match else [],
    )
    return result


def list_unmatched_payments(customer_id: str | None = None) -> dict[str, Any]:
    rows = [_clean(r) for r in repo.list_payments(customer_id=customer_id, unmatched_only=True)]
    result = {"status": "success", "count": len(rows), "payments": rows, "needs_review": len(rows) > 0}
    result["evidence"] = record_evidence(
        agent="payments_agent", action="list_unmatched_payments",
        inputs={"customer_id": customer_id}, outputs={"count": len(rows)},
        sources=[repo.source_label()],
    )
    return result


def suggest_payment_match(payment_id: str) -> dict[str, Any]:
    payment_id = payment_id.strip().upper()
    payment = repo.get_payment(payment_id)
    if not payment:
        result = {"status": "not_found", "payment_id": payment_id, "needs_review": True}
        result["evidence"] = record_evidence(
            agent="payments_agent", action="suggest_payment_match",
            inputs={"payment_id": payment_id}, outputs=result, sources=[],
        )
        return result
    candidates = []
    for inv in repo.list_invoices(customer_id=payment["customer_id"], open_only=True):
        score, reasons = 0.0, []
        ref = (payment.get("reference") or "").upper()
        if inv["invoice_id"] in ref:
            score += 0.7
            reasons.append("invoice_id_in_reference")
        if inv.get("po_number") and str(inv["po_number"]) in ref:
            score += 0.4
            reasons.append("po_in_reference")
        amount_delta = abs(float(inv["amount"]) - float(payment["amount"]))
        if amount_delta <= max(1.0, float(inv["amount"]) * 0.005):
            score += 0.5
            reasons.append("amount_within_tolerance")
        elif float(payment["amount"]) < float(inv["amount"]):
            score += 0.2
            reasons.append("possible_partial")
        if score > 0:
            candidates.append({
                "invoice_id": inv["invoice_id"], "score": round(score, 2), "reasons": reasons,
                "invoice_amount": inv["amount"], "invoice_status": inv["status"],
            })
    candidates.sort(key=lambda c: c["score"], reverse=True)
    result = {
        "status": "success", "payment": _clean(payment), "candidates": candidates[:5],
        "needs_review": True, "recommendation": candidates[0]["invoice_id"] if candidates else None,
    }
    result["evidence"] = record_evidence(
        agent="payments_agent", action="suggest_payment_match",
        inputs={"payment_id": payment_id},
        outputs={"recommendation": result["recommendation"], "candidate_count": len(candidates)},
        sources=[repo.source_label(), "policy:POL-RECON-01"],
    )
    return result
