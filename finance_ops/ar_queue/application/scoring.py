"""Application scoring — domain match rules + catalog I/O."""

from __future__ import annotations

from typing import Any

from finance_ops.ar_queue.adapters.warehouse_payments import (
    DEFAULT_PAYMENT_CATALOG,
    WarehousePaymentCatalog,
)
from finance_ops.ar_queue.domain.matching import (
    score_against_invoices,
    score_payments_batch_cpu,
)


def score_payment_match(
    payment_id: str,
    *,
    payment: dict[str, Any] | None = None,
    invoices: list[dict[str, Any]] | None = None,
    catalog: WarehousePaymentCatalog | None = None,
) -> dict[str, Any]:
    """Pure match scoring against warehouse (no breaker / evidence)."""
    catalog = catalog or DEFAULT_PAYMENT_CATALOG
    payment_id = payment_id.strip().upper()
    payment = payment or catalog.get_payment(payment_id)
    if not payment:
        return {"status": "not_found", "payment_id": payment_id, "needs_review": True}
    if invoices is None:
        invoices = catalog.list_invoices(
            customer_id=payment["customer_id"], open_only=True
        )
    return score_against_invoices(payment, invoices)


def score_payments_batch(
    payments: list[dict[str, Any]],
    *,
    invoices_by_customer: dict[str, list[dict[str, Any]]] | None = None,
    catalog: WarehousePaymentCatalog | None = None,
) -> dict[str, dict[str, Any]]:
    """Batch-score payments with one invoice preload."""
    catalog = catalog or DEFAULT_PAYMENT_CATALOG
    if invoices_by_customer is None:
        open_invoices = catalog.list_invoices(open_only=True)
        invoices_by_customer = {}
        for inv in open_invoices:
            invoices_by_customer.setdefault(str(inv.get("customer_id")), []).append(
                inv
            )
    return score_payments_batch_cpu(payments, invoices_by_customer)
