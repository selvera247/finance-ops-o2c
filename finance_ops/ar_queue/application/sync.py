"""Use case: materialize open AR exceptions from warehouse feeds."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from finance_ops.ar_queue.adapters.ttl_cache import (
    DEFAULT_QUEUE_CACHE,
    MATCH_TTL,
    TtlCacheAdapter,
)
from finance_ops.ar_queue.adapters.warehouse_exceptions import (
    DEFAULT_EXCEPTION_STORE,
    WarehouseExceptionStore,
    preserve_terminal_status,
)
from finance_ops.ar_queue.adapters.warehouse_payments import (
    DEFAULT_PAYMENT_CATALOG,
    WarehousePaymentCatalog,
)
from finance_ops.ar_queue.domain.exception_rows import (
    cash_app_exception_row,
    hubspot_gap_exception_row,
    portal_exception_row,
)
from finance_ops.ar_queue.domain.matching import score_payments_batch_cpu
from finance_ops.ar_queue.domain.portal_classify import (
    SPIKE_B_WALKTHROUGH,
    classify_portal_row,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def upsert_exception(
    row: dict[str, Any],
    *,
    invalidate: bool = True,
    store: WarehouseExceptionStore | None = None,
    cache: TtlCacheAdapter | None = None,
) -> str:
    """Insert or update one ar_exceptions row. Returns exception_id."""
    store = store or DEFAULT_EXCEPTION_STORE
    cache = cache or DEFAULT_QUEUE_CACHE
    store.ensure_schema()
    now = _now()
    eid = row["exception_id"]
    existing = store.get_existing([eid])
    prev = existing.get(eid)
    opened_at = prev["opened_at"] if prev else now
    row = preserve_terminal_status(row, prev)
    store.replace_row(row, opened_at=opened_at, now=now)
    if invalidate:
        cache.invalidate_queue()
    return eid


def upsert_exceptions_batch(
    rows: list[dict[str, Any]],
    *,
    store: WarehouseExceptionStore | None = None,
    cache: TtlCacheAdapter | None = None,
) -> list[str]:
    """Batch upsert in one DuckDB connection; single cache invalidation."""
    if not rows:
        return []
    store = store or DEFAULT_EXCEPTION_STORE
    cache = cache or DEFAULT_QUEUE_CACHE
    store.ensure_schema()
    now = _now()
    ids = [r["exception_id"] for r in rows]
    existing_map = store.get_existing(ids)
    prepared: list[tuple[dict[str, Any], Any]] = []
    synced: list[str] = []
    for row in rows:
        eid = row["exception_id"]
        prev = existing_map.get(eid)
        opened_at = prev["opened_at"] if prev else now
        row = preserve_terminal_status(row, prev)
        prepared.append((row, opened_at))
        synced.append(eid)
    store.replace_rows_batch(prepared, now=now)
    cache.invalidate_queue()
    return synced


def sync_from_warehouse(
    *,
    workflow_run_id: str | None = None,
    include_portal: bool = True,
    include_hubspot_gaps: bool = True,
    payment_ids: list[str] | None = None,
    store: WarehouseExceptionStore | None = None,
    catalog: WarehousePaymentCatalog | None = None,
    cache: TtlCacheAdapter | None = None,
) -> dict[str, Any]:
    """Materialize open AR exceptions from payments (+ optional portal / gaps)."""
    store = store or DEFAULT_EXCEPTION_STORE
    catalog = catalog or DEFAULT_PAYMENT_CATALOG
    cache = cache or DEFAULT_QUEUE_CACHE
    store.ensure_schema()
    pending_rows: list[dict[str, Any]] = []

    if payment_ids:
        payments = []
        for pid in payment_ids:
            row = catalog.get_payment(pid)
            if row:
                payments.append(row)
    else:
        payments = catalog.list_payments(unmatched_only=True)

    open_invoices = catalog.list_invoices(open_only=True)
    invoices_by_customer: dict[str, list[dict[str, Any]]] = {}
    for inv in open_invoices:
        invoices_by_customer.setdefault(str(inv.get("customer_id")), []).append(inv)
    scored_map = score_payments_batch_cpu(payments, invoices_by_customer)

    for pay in payments:
        pid = str(pay.get("payment_id") or "").upper()
        if not pid:
            continue
        scored = scored_map.get(pid) or {
            "status": "not_found",
            "candidates": [],
            "recommendation": None,
        }
        cache.set(f"ar:match:{pid}", scored, MATCH_TTL)
        built = cash_app_exception_row(
            payment=pay, scored=scored, workflow_run_id=workflow_run_id
        )
        if built:
            pending_rows.append(built)

    if include_portal:
        extracts = catalog.portal_extracts_by_external_id()
        for cid in SPIKE_B_WALKTHROUGH:
            classified = classify_portal_row(cid, extracts.get(cid))
            if classified.get("status") != "success":
                continue
            pending_rows.append(
                portal_exception_row(
                    claim_id=cid,
                    classified=classified,
                    workflow_run_id=workflow_run_id,
                )
            )

    gap_count = 0
    if include_hubspot_gaps:
        from finance_ops.runtime.ar_feed import triage_hubspot_gaps

        gaps = triage_hubspot_gaps(use_live_hubspot=False)
        for g in gaps.get("gaps") or []:
            built = hubspot_gap_exception_row(
                gap=g, workflow_run_id=workflow_run_id
            )
            if not built:
                continue
            gap_count += 1
            pending_rows.append(built)

    synced = upsert_exceptions_batch(
        pending_rows, store=store, cache=cache
    )
    return {
        "status": "success",
        "synced_count": len(synced),
        "exception_ids": synced,
        "payment_count": len(payments),
        "hubspot_gap_count": gap_count,
        "needs_review": len(synced) > 0,
    }
