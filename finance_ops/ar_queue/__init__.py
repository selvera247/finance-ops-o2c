"""AR exception queue — clean architecture bounded context.

Layers
------
- ``domain`` — pure scoring, classification, IDs, SKUs, statuses
- ``application`` — sync / query / lifecycle / scoring use cases
- ``ports`` — ExceptionStore / PaymentCatalog / CachePort protocols
- ``adapters`` — DuckDB warehouse + TTL cache implementations

Legacy import paths (``finance_ops.services.queue_service``, payment/portal
tools) remain as thin compatibility façades — behavior unchanged.
"""

from finance_ops.ar_queue.application import (
    get_exception,
    list_exceptions,
    mark_pending_hitl,
    mark_resolved,
    queue_metrics,
    score_payment_match,
    score_payments_batch,
    sync_from_warehouse,
    upsert_exception,
    upsert_exceptions_batch,
)
from finance_ops.ar_queue.domain import list_skus, sku_for_lane

__all__ = [
    "get_exception",
    "list_exceptions",
    "list_skus",
    "mark_pending_hitl",
    "mark_resolved",
    "queue_metrics",
    "score_payment_match",
    "score_payments_batch",
    "sku_for_lane",
    "sync_from_warehouse",
    "upsert_exception",
    "upsert_exceptions_batch",
]
