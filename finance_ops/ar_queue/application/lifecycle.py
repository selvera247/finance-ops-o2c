"""Use cases: pending HITL + resolve (+ meter) for exceptions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from finance_ops.ar_queue.adapters.ttl_cache import (
    DEFAULT_QUEUE_CACHE,
    TtlCacheAdapter,
)
from finance_ops.ar_queue.adapters.warehouse_exceptions import (
    DEFAULT_EXCEPTION_STORE,
    WarehouseExceptionStore,
)
from finance_ops.ar_queue.application.queries import get_exception
from finance_ops.ar_queue.application.sync import upsert_exception
from finance_ops.ar_queue.domain.ids import exception_id, lane_prefix
from finance_ops.ar_queue.domain.skus import sku_for_lane


def _now() -> datetime:
    return datetime.now(timezone.utc)


def mark_pending_hitl(
    *,
    source_id: str,
    lane: str = "cash_app",
    approval_id: str,
    store: WarehouseExceptionStore | None = None,
    cache: TtlCacheAdapter | None = None,
) -> dict[str, Any]:
    prefix = lane_prefix(lane)
    eid = exception_id(prefix, source_id)
    got = get_exception(eid, store=store)
    if got.get("status") != "success":
        return got
    row = got["exception"]
    row["status"] = "pending_hitl"
    row["approval_id"] = approval_id
    upsert_exception(row, store=store, cache=cache)
    return {"status": "success", "exception_id": eid, "approval_id": approval_id}


def mark_resolved(
    *,
    source_id: str,
    lane: str = "cash_app",
    invoice_id: str | None = None,
    store: WarehouseExceptionStore | None = None,
    cache: TtlCacheAdapter | None = None,
) -> dict[str, Any]:
    """Mark exception resolved and write a billable meter event."""
    store = store or DEFAULT_EXCEPTION_STORE
    cache = cache or DEFAULT_QUEUE_CACHE
    store.ensure_schema()
    prefix = lane_prefix(lane)
    eid = exception_id(prefix, source_id)
    got = get_exception(eid, store=store)
    if got.get("status") != "success":
        return got
    row = got["exception"]
    now = _now()
    row["status"] = "resolved"
    row["resolved_at"] = now
    if invoice_id:
        row["recommended_invoice_id"] = invoice_id
    upsert_exception(row, invalidate=False, store=store, cache=cache)

    event_id = f"MTR-{uuid.uuid4().hex[:12]}"
    sku = row.get("sku_code") or sku_for_lane(lane)
    store.insert_meter_event(
        event_id=event_id,
        sku=sku,
        exception_id=eid,
        customer_id=row.get("customer_id"),
        now=now,
        meta={"invoice_id": invoice_id, "source_id": source_id},
    )
    cache.invalidate_queue()
    return {
        "status": "success",
        "exception_id": eid,
        "meter_event_id": event_id,
        "sku_code": sku,
    }
