"""Builders that turn scored/classified inputs into ar_exceptions row dicts."""

from __future__ import annotations

from typing import Any

from finance_ops.ar_queue.domain.ids import exception_id


def cash_app_exception_row(
    *,
    payment: dict[str, Any],
    scored: dict[str, Any],
    workflow_run_id: str | None = None,
) -> dict[str, Any] | None:
    pid = str(payment.get("payment_id") or "").upper()
    if not pid:
        return None
    top = (scored.get("candidates") or [None])[0]
    return {
        "exception_id": exception_id("cash_app", pid),
        "lane": "cash_app",
        "source_type": "payment",
        "source_id": pid,
        "customer_id": payment.get("customer_id"),
        "amount": payment.get("amount"),
        "currency": payment.get("currency") or "USD",
        "status": "open",
        "disposition": "suggest_match",
        "recommended_invoice_id": scored.get("recommendation"),
        "match_score": (top or {}).get("score"),
        "match_reasons": (top or {}).get("reasons") or [],
        "workflow_run_id": workflow_run_id,
        "sku_code": "resolve.cash_app",
        "payload": {
            "payment": {k: payment.get(k) for k in ("reference", "status")}
        },
    }


def portal_exception_row(
    *,
    claim_id: str,
    classified: dict[str, Any],
    workflow_run_id: str | None = None,
) -> dict[str, Any]:
    return {
        "exception_id": exception_id("portal", claim_id),
        "lane": "portal_remittance",
        "source_type": "portal_extract",
        "source_id": claim_id,
        "customer_id": None,
        "amount": classified.get("amount"),
        "currency": "USD",
        "status": "open",
        "disposition": classified.get("disposition"),
        "recommended_invoice_id": (
            (classified.get("suggested_invoice_ids") or [None])[0]
        ),
        "match_score": None,
        "match_reasons": classified.get("suggested_invoice_ids") or [],
        "workflow_run_id": workflow_run_id,
        "sku_code": "resolve.portal",
        "payload": {"hitl_kind": classified.get("hitl_kind")},
    }


def hubspot_gap_exception_row(
    *,
    gap: dict[str, Any],
    workflow_run_id: str | None = None,
) -> dict[str, Any] | None:
    cust = str(gap.get("customer_id") or "").upper()
    if not cust:
        return None
    return {
        "exception_id": exception_id("hubspot", cust),
        "lane": "hubspot_gap",
        "source_type": "hubspot_gap",
        "source_id": cust,
        "customer_id": cust,
        "amount": float(gap.get("sold") or 0) - float(gap.get("invoiced_total") or 0),
        "currency": "USD",
        "status": "open",
        "disposition": ",".join(gap.get("gaps") or []),
        "recommended_invoice_id": None,
        "match_score": None,
        "match_reasons": gap.get("gaps") or [],
        "workflow_run_id": workflow_run_id,
        "sku_code": "resolve.cash_app",
        "payload": gap,
    }
