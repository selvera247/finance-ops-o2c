"""Use cases: list / get exceptions and queue metrics."""

from __future__ import annotations

from typing import Any

from finance_ops.ar_queue.adapters.ttl_cache import (
    DEFAULT_QUEUE_CACHE,
    LIST_TTL,
    METRICS_TTL,
    TtlCacheAdapter,
)
from finance_ops.ar_queue.adapters.warehouse_exceptions import (
    DEFAULT_EXCEPTION_STORE,
    WarehouseExceptionStore,
)
from finance_ops.ar_queue.domain.statuses import OPEN_STATUSES


def list_exceptions(
    *,
    status: str | None = "open",
    lane: str | None = None,
    limit: int = 50,
    store: WarehouseExceptionStore | None = None,
    cache: TtlCacheAdapter | None = None,
) -> dict[str, Any]:
    store = store or DEFAULT_EXCEPTION_STORE
    cache = cache or DEFAULT_QUEUE_CACHE
    limit = max(1, min(int(limit), 200))
    cache_key = f"ar:exceptions:list:{status or 'any'}:{lane or 'any'}:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    store.ensure_schema()
    rows = store.list_rows(status=status, lane=lane, limit=limit)
    result = {
        "status": "success",
        "count": len(rows),
        "exceptions": rows,
        "needs_review": any(r.get("status") in OPEN_STATUSES for r in rows),
    }
    cache.set(cache_key, result, LIST_TTL)
    return result


def get_exception(
    exception_id: str,
    *,
    store: WarehouseExceptionStore | None = None,
) -> dict[str, Any]:
    store = store or DEFAULT_EXCEPTION_STORE
    store.ensure_schema()
    row = store.fetch_by_id(exception_id)
    if not row:
        return {
            "status": "not_found",
            "exception_id": exception_id,
            "needs_review": True,
        }
    return {
        "status": "success",
        "exception": row,
        "needs_review": row.get("status") in OPEN_STATUSES,
    }


def queue_metrics(
    *,
    use_cache: bool = True,
    store: WarehouseExceptionStore | None = None,
    cache: TtlCacheAdapter | None = None,
) -> dict[str, Any]:
    """Product metrics from ar_exceptions + HITL aggregate."""
    store = store or DEFAULT_EXCEPTION_STORE
    cache = cache or DEFAULT_QUEUE_CACHE
    if use_cache:
        cached = cache.get("ar:metrics:v1")
        if cached is not None:
            return cached

    from finance_ops.runtime.exception_queue import build_ar_exception_queue

    store.ensure_schema()
    snap = build_ar_exception_queue()
    rows = store.list_status_amounts()
    by_status: dict[str, int] = {}
    open_usd = 0.0
    for r in rows:
        st = str(r.get("status") or "")
        by_status[st] = by_status.get(st, 0) + 1
        if st in OPEN_STATUSES:
            open_usd += float(r.get("amount") or 0)
    result = {
        "status": "success",
        "story": snap.get("story"),
        "projection": {
            "exception_count": len(rows),
            "by_status": by_status,
            "open_exception_usd": round(open_usd, 2),
            "billable_resolves": store.count_billable_resolves(),
        },
        "legacy_metrics": snap.get("metrics"),
        "cache": cache.stats(),
        "needs_review": (by_status.get("open", 0) + by_status.get("pending_hitl", 0))
        > 0,
    }
    if use_cache:
        cache.set("ar:metrics:v1", result, METRICS_TTL)
    return result
