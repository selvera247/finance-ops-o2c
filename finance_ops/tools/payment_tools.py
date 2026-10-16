from __future__ import annotations

from typing import Any

from data_plane import repository as repo
from finance_ops.lib.evidence import record_evidence


def lookup_payment(payment_id: str) -> dict[str, Any]:
    """Look up a payment by payment_id (e.g. PAY-9002)."""
    payment_id = payment_id.strip().upper()
    match = repo.get_payment(payment_id)
    if not match:
        result = {
            "status": "not_found",
            "payment_id": payment_id,
            "needs_review": True,
        }
    else:
        result = {
            "status": "success",
            "payment": {
                k: (str(v) if hasattr(v, "isoformat") else v) for k, v in match.items()
            },
            "needs_review": False,
        }

    evidence = record_evidence(
        agent="payments_agent",
        action="lookup_payment",
        inputs={"payment_id": payment_id},
        outputs=result,
        sources=[repo.source_label()] if match else [],
    )
    result["evidence"] = evidence
    return result


def list_unmatched_payments(customer_id: str | None = None) -> dict[str, Any]:
    """List payments that are unmatched or only partially applied."""
    rows = repo.list_payments(customer_id=customer_id, unmatched_only=True)
    clean = [
        {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in row.items()}
        for row in rows
    ]
    result = {
        "status": "success",
        "count": len(clean),
        "payments": clean,
        "needs_review": len(clean) > 0,
    }
    evidence = record_evidence(
        agent="payments_agent",
        action="list_unmatched_payments",
        inputs={"customer_id": customer_id},
        outputs={"count": len(clean)},
        sources=[repo.source_label()],
    )
    result["evidence"] = evidence
    return result


def suggest_payment_match(payment_id: str) -> dict[str, Any]:
    """Suggest invoice matches for an unmatched/partial payment using simple rules."""
    payment_id = payment_id.strip().upper()
    payment = repo.get_payment(payment_id)
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
    for inv in repo.list_invoices(customer_id=payment["customer_id"], open_only=True):
        score = 0.0
        reasons: list[str] = []
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
    payment_clean = {
        k: (str(v) if hasattr(v, "isoformat") else v) for k, v in payment.items()
    }
    result = {
        "status": "success",
        "payment": payment_clean,
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
        sources=[repo.source_label(), "policy:POL-RECON-01"],
    )
    result["evidence"] = evidence
    return result
