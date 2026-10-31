"""Compatibility façade — implementation lives in ``finance_ops.ar_queue``.

Prefer importing from ``finance_ops.ar_queue`` (or ``.application``) in new code.
"""

from __future__ import annotations

from finance_ops.ar_queue.adapters.ttl_cache import (
    DEFAULT_QUEUE_CACHE,
    LIST_TTL,
    MATCH_TTL,
    METRICS_TTL,
)
from finance_ops.ar_queue.application.lifecycle import mark_pending_hitl, mark_resolved
from finance_ops.ar_queue.application.queries import (
    get_exception,
    list_exceptions,
    queue_metrics,
)
from finance_ops.ar_queue.application.sync import (
    sync_from_warehouse,
    upsert_exception,
    upsert_exceptions_batch,
)
from finance_ops.ar_queue.domain.ids import exception_id as _exception_id
from finance_ops.ar_queue.domain.statuses import OPEN_STATUSES


def invalidate_queue_cache() -> None:
    DEFAULT_QUEUE_CACHE.invalidate_queue()


__all__ = [
    "LIST_TTL",
    "MATCH_TTL",
    "METRICS_TTL",
    "OPEN_STATUSES",
    "_exception_id",
    "get_exception",
    "invalidate_queue_cache",
    "list_exceptions",
    "mark_pending_hitl",
    "mark_resolved",
    "queue_metrics",
    "sync_from_warehouse",
    "upsert_exception",
    "upsert_exceptions_batch",
]
