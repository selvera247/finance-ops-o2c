"""Side effects after HITL decisions (e.g. apply cash-app match on approve)."""

from __future__ import annotations

from typing import Any

from finance_ops.runtime.hitl import PendingApproval


def after_decision(item: PendingApproval) -> dict[str, Any]:
    """Run post-decision effects. Safe to call from tools and HITL server."""
    if item.status != "approved":
        return {"applied": False, "reason": f"status_{item.status}"}

    kind = (item.kind or "").strip().lower()
    if kind in {"cash_app_match", "payment_match", "cash_app"}:
        payment_id = str(item.payload.get("payment_id") or "")
        invoice_id = str(
            item.payload.get("invoice_id")
            or item.payload.get("recommended_invoice_id")
            or ""
        )
        if not payment_id or not invoice_id:
            return {
                "applied": False,
                "reason": "missing_payment_or_invoice",
                "payload": item.payload,
            }
        from data_plane import repository as repo

        result = repo.apply_payment_match(payment_id, invoice_id)
        return {
            "applied": bool(result.get("ok")),
            "kind": kind,
            "payment_id": payment_id,
            "invoice_id": invoice_id,
            "result": result,
        }

    return {"applied": False, "reason": "no_effect_for_kind", "kind": kind}
