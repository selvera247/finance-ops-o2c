from __future__ import annotations

from typing import Any

from finance_ops.lib.evidence import record_evidence
from finance_ops.lib.fixtures import invoices, payments


def lookup_payment(payment_id: str) -> dict[str, Any]:
    """Look up a payment by payment_id (e.g. PAY-9002)."""
    payment_id = payment_id.strip().upper()
    match = next((p for p in payments() if p["payment_id"] == payment_id), None)
    if not match:
        result = {
            "status": "not_found",
            "payment_id": payment_id,
            "needs_review": True,
        }
    else:
        result = {"status": "success", "payment": match, "needs_review": False}

    evidence = record_evidence(
        agent="payments_agent",
        action="lookup_payment",
        inputs={"payment_id": payment_id},
        outputs=result,
        sources=["fixture:payments.json"] if match else [],
    )
    result["evidence"] = evidence
    return result


def list_unmatched_payments(customer_id: str | None = None) -> dict[str, Any]:
    """List payments that are unmatched or only partially applied."""
    rows = [
        p
        for p in payments()
        if p["status"] in {"unmatched", "partial"}
        and (customer_id is None or p["customer_id"] == customer_id)
    ]
    result = {
        "status": "success",
        "count": len(rows),
        "payments": rows,
        "needs_review": len(rows) > 0,
    }
    evidence = record_evidence(
        agent="payments_agent",
        action="list_unmatched_payments",
        inputs={"customer_id": customer_id},
        outputs={"count": len(rows)},
        sources=["fixture:payments.json"],
    )
    result["evidence"] = evidence
    return result


def suggest_payment_match(payment_id: str) -> dict[str, Any]:
    """Suggest invoice matches for an unmatched/partial payment using simple rules."""
    payment_id = payment_id.strip().upper()
    payment = next((p for p in payments() if p["payment_id"] == payment_id), None)
    if not payment:
        result = {
            "status": "not_found",
            "payment_id": payment_id,
            "needs_review": True,
        }
        evidence = record_evidence(
            agent="payments_agent",
            action="suggest_payment_match",
            inputs={"payment_id": payment_id},
            outputs=result,
            sources=[],
        )
        result["evidence"] = evidence
        return result

    candidates = []
    for inv in invoices():
        if inv["customer_id"] != payment["customer_id"]:
            continue
        if inv["status"] not in {"open", "past_due"}:
            continue
        score = 0.0
        reasons: list[str] = []
        ref = (payment.get("reference") or "").upper()
        if inv["invoice_id"] in ref:
            score += 0.7
            reasons.append("invoice_id_in_reference")
        if inv.get("po_number") and inv["po_number"] in ref:
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
    result = {
        "status": "success",
        "payment": payment,
        "candidates": candidates[:5],
        "needs_review": True,
        "recommendation": candidates[0]["invoice_id"] if candidates else None,
    }
    evidence = record_evidence(
        agent="payments_agent",
        action="suggest_payment_match",
        inputs={"payment_id": payment_id},
        outputs={
            "recommendation": result["recommendation"],
            "candidate_count": len(candidates),
        },
        sources=["fixture:payments.json", "fixture:invoices.json", "policy:POL-RECON-01"],
    )
    result["evidence"] = evidence
    return result
