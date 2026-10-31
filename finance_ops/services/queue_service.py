"""AR exception queue service — materialize, list, metrics, meter (MVP)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from finance_ops.runtime.cache import DEFAULT_CACHE
from finance_ops.services.sku_catalog import sku_for_lane

METRICS_TTL = 15.0
LIST_TTL = 10.0
MATCH_TTL = 60.0

OPEN_STATUSES = frozenset({"open", "pending_hitl", "escalated"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure() -> None:
    from data_plane.warehouse import db

    db.init_schema()


def _clean(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        elif k.endswith("_json") and isinstance(v, str) and v:
            try:
                out[k.replace("_json", "")] = json.loads(v)
            except json.JSONDecodeError:
                out[k] = v
        else:
            out[k] = v
    # normalize aliases
    if "match_reasons" not in out and "match_reasons_json" in row:
        raw = row.get("match_reasons_json")
        if isinstance(raw, str) and raw:
            try:
                out["match_reasons"] = json.loads(raw)
            except json.JSONDecodeError:
                out["match_reasons"] = []
        else:
            out["match_reasons"] = []
    if "payload" not in out and row.get("payload_json"):
        try:
            out["payload"] = json.loads(str(row["payload_json"]))
        except json.JSONDecodeError:
            out["payload"] = {}
    return out


def invalidate_queue_cache() -> None:
    DEFAULT_CACHE.invalidate_prefix("ar:")


def _exception_id(lane: str, source_id: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in source_id.upper())
    return f"EXE-{lane[:12]}-{safe[:40]}"


def _row_params(row: dict[str, Any], *, opened_at: Any, now: datetime) -> list[Any]:
    reasons = row.get("match_reasons") or []
    payload = row.get("payload") or {}
    return [
        row["exception_id"],
        row.get("lane"),
        row.get("source_type"),
        row.get("source_id"),
        row.get("customer_id"),
        float(row.get("amount") or 0),
        row.get("currency") or "USD",
        row.get("status") or "open",
        row.get("disposition"),
        row.get("recommended_invoice_id"),
        row.get("match_score"),
        json.dumps(reasons),
        row.get("approval_id"),
        row.get("workflow_run_id"),
        row.get("evidence_id"),
        row.get("sku_code") or sku_for_lane(str(row.get("lane") or "")),
        json.dumps(payload),
        opened_at,
        now,
        row.get("resolved_at"),
    ]


def upsert_exception(row: dict[str, Any], *, invalidate: bool = True) -> str:
    """Insert or update one ar_exceptions row. Returns exception_id."""
    _ensure()
    from data_plane.warehouse import db

    now = _now()
    eid = row["exception_id"]
    existing = db.query_dicts(
        "SELECT exception_id, status, opened_at FROM ar_exceptions WHERE exception_id = ?",
        [eid],
    )
    opened_at = existing[0]["opened_at"] if existing else now
    if existing and str(existing[0].get("status")) in {"resolved", "rejected"}:
        if row.get("status") in OPEN_STATUSES:
            row = {**row, "status": existing[0]["status"]}

    db.execute("DELETE FROM ar_exceptions WHERE exception_id = ?", [eid])
    db.execute(
        "INSERT INTO ar_exceptions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        _row_params(row, opened_at=opened_at, now=now),
    )
    if invalidate:
        invalidate_queue_cache()
    return eid


def upsert_exceptions_batch(rows: list[dict[str, Any]]) -> list[str]:
    """Batch upsert in one DuckDB connection; single cache invalidation."""
    if not rows:
        return []
    _ensure()
    from data_plane.warehouse import db

    now = _now()
    ids = [r["exception_id"] for r in rows]
    existing_map: dict[str, dict[str, Any]] = {}
    # Chunk IN clause for large syncs
    con = db.connect()
    try:
        for i in range(0, len(ids), 200):
            chunk = ids[i : i + 200]
            placeholders = ",".join("?" * len(chunk))
            cur = con.execute(
                f"SELECT exception_id, status, opened_at FROM ar_exceptions "
                f"WHERE exception_id IN ({placeholders})",
                chunk,
            )
            cols = [d[0] for d in cur.description]
            for tup in cur.fetchall():
                rec = dict(zip(cols, tup))
                existing_map[str(rec["exception_id"])] = rec

        synced: list[str] = []
        for row in rows:
            eid = row["exception_id"]
            prev = existing_map.get(eid)
            opened_at = prev["opened_at"] if prev else now
            status = row.get("status") or "open"
            if prev and str(prev.get("status")) in {"resolved", "rejected"}:
                if status in OPEN_STATUSES:
                    status = str(prev["status"])
                    row = {**row, "status": status}
            con.execute("DELETE FROM ar_exceptions WHERE exception_id = ?", [eid])
            con.execute(
                "INSERT INTO ar_exceptions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                _row_params(row, opened_at=opened_at, now=now),
            )
            synced.append(eid)
    finally:
        con.close()
    invalidate_queue_cache()
    return synced


def sync_from_warehouse(
    *,
    workflow_run_id: str | None = None,
    include_portal: bool = True,
    include_hubspot_gaps: bool = True,
    payment_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Materialize open AR exceptions from payments (+ optional portal / gaps)."""
    from data_plane import repository as repo
    from finance_ops.runtime.ar_feed import triage_hubspot_gaps
    from finance_ops.tools.payment_tools import score_payments_batch
    from finance_ops.tools.portal_spike_tools import (
        SPIKE_B_WALKTHROUGH,
        classify_portal_row,
    )

    _ensure()
    pending_rows: list[dict[str, Any]] = []

    if payment_ids:
        payments = []
        for pid in payment_ids:
            row = repo.get_payment(pid)
            if row:
                payments.append(row)
    else:
        payments = repo.list_payments(unmatched_only=True)

    # One invoice preload + CPU scoring (avoids N+1 warehouse round-trips).
    scored_map = score_payments_batch(payments)
    for pay in payments:
        pid = str(pay.get("payment_id") or "").upper()
        if not pid:
            continue
        scored = scored_map.get(pid) or {
            "status": "not_found",
            "candidates": [],
            "recommendation": None,
        }
        DEFAULT_CACHE.set(f"ar:match:{pid}", scored, MATCH_TTL)
        top = (scored.get("candidates") or [None])[0]
        pending_rows.append(
            {
                "exception_id": _exception_id("cash_app", pid),
                "lane": "cash_app",
                "source_type": "payment",
                "source_id": pid,
                "customer_id": pay.get("customer_id"),
                "amount": pay.get("amount"),
                "currency": pay.get("currency") or "USD",
                "status": "open",
                "disposition": "suggest_match",
                "recommended_invoice_id": scored.get("recommendation"),
                "match_score": (top or {}).get("score"),
                "match_reasons": (top or {}).get("reasons") or [],
                "workflow_run_id": workflow_run_id,
                "sku_code": "resolve.cash_app",
                "payload": {
                    "payment": {k: pay.get(k) for k in ("reference", "status")}
                },
            }
        )

    if include_portal:
        # Single portal scan, then classify in memory.
        extracts = {
            str(r.get("external_id") or "").upper(): r
            for r in repo.portal_extracts()
        }
        for cid in SPIKE_B_WALKTHROUGH:
            classified = classify_portal_row(cid, extracts.get(cid))
            if classified.get("status") != "success":
                continue
            pending_rows.append(
                {
                    "exception_id": _exception_id("portal", cid),
                    "lane": "portal_remittance",
                    "source_type": "portal_extract",
                    "source_id": cid,
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
            )

    gap_count = 0
    if include_hubspot_gaps:
        gaps = triage_hubspot_gaps(use_live_hubspot=False)
        for g in gaps.get("gaps") or []:
            cust = str(g.get("customer_id") or "").upper()
            if not cust:
                continue
            gap_count += 1
            pending_rows.append(
                {
                    "exception_id": _exception_id("hubspot", cust),
                    "lane": "hubspot_gap",
                    "source_type": "hubspot_gap",
                    "source_id": cust,
                    "customer_id": cust,
                    "amount": float(g.get("sold") or 0)
                    - float(g.get("invoiced_total") or 0),
                    "currency": "USD",
                    "status": "open",
                    "disposition": ",".join(g.get("gaps") or []),
                    "recommended_invoice_id": None,
                    "match_score": None,
                    "match_reasons": g.get("gaps") or [],
                    "workflow_run_id": workflow_run_id,
                    "sku_code": "resolve.cash_app",
                    "payload": g,
                }
            )

    synced = upsert_exceptions_batch(pending_rows)
    return {
        "status": "success",
        "synced_count": len(synced),
        "exception_ids": synced,
        "payment_count": len(payments),
        "hubspot_gap_count": gap_count,
        "needs_review": len(synced) > 0,
    }


def list_exceptions(
    *,
    status: str | None = "open",
    lane: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    limit = max(1, min(int(limit), 200))
    cache_key = f"ar:exceptions:list:{status or 'any'}:{lane or 'any'}:{limit}"
    cached = DEFAULT_CACHE.get(cache_key)
    if cached is not None:
        return cached

    _ensure()
    from data_plane.warehouse import db

    sql = "SELECT * FROM ar_exceptions WHERE 1=1"
    params: list[Any] = []
    if status:
        if status == "open":
            sql += " AND status IN ('open','pending_hitl','escalated')"
        else:
            sql += " AND status = ?"
            params.append(status)
    if lane:
        sql += " AND lane = ?"
        params.append(lane)
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    rows = [_clean(r) for r in db.query_dicts(sql, params)]
    result = {
        "status": "success",
        "count": len(rows),
        "exceptions": rows,
        "needs_review": any(r.get("status") in OPEN_STATUSES for r in rows),
    }
    DEFAULT_CACHE.set(cache_key, result, LIST_TTL)
    return result


def get_exception(exception_id: str) -> dict[str, Any]:
    _ensure()
    from data_plane.warehouse import db

    rows = db.query_dicts(
        "SELECT * FROM ar_exceptions WHERE exception_id = ?",
        [exception_id.strip()],
    )
    if not rows:
        return {
            "status": "not_found",
            "exception_id": exception_id,
            "needs_review": True,
        }
    return {
        "status": "success",
        "exception": _clean(rows[0]),
        "needs_review": rows[0].get("status") in OPEN_STATUSES,
    }


def mark_pending_hitl(
    *,
    source_id: str,
    lane: str = "cash_app",
    approval_id: str,
) -> dict[str, Any]:
    eid = _exception_id(lane if lane != "portal_remittance" else "portal", source_id)
    if lane == "portal_remittance":
        eid = _exception_id("portal", source_id)
    got = get_exception(eid)
    if got.get("status") != "success":
        return got
    row = got["exception"]
    row["status"] = "pending_hitl"
    row["approval_id"] = approval_id
    upsert_exception(row)
    return {"status": "success", "exception_id": eid, "approval_id": approval_id}


def mark_resolved(
    *,
    source_id: str,
    lane: str = "cash_app",
    invoice_id: str | None = None,
) -> dict[str, Any]:
    """Mark exception resolved and write a billable meter event."""
    _ensure()
    from data_plane.warehouse import db

    prefix = "portal" if lane == "portal_remittance" else (
        "hubspot" if lane == "hubspot_gap" else "cash_app"
    )
    eid = _exception_id(prefix, source_id)
    got = get_exception(eid)
    if got.get("status") != "success":
        return got
    row = got["exception"]
    now = _now()
    row["status"] = "resolved"
    row["resolved_at"] = now
    if invoice_id:
        row["recommended_invoice_id"] = invoice_id
    upsert_exception(row)

    event_id = f"MTR-{uuid.uuid4().hex[:12]}"
    sku = row.get("sku_code") or sku_for_lane(lane)
    db.execute("DELETE FROM sku_meter_events WHERE event_id = ?", [event_id])
    db.execute(
        "INSERT INTO sku_meter_events VALUES (?,?,?,?,?,?,?,?,?)",
        [
            event_id,
            sku,
            eid,
            row.get("customer_id"),
            1.0,
            "exception",
            "billable",
            now,
            json.dumps({"invoice_id": invoice_id, "source_id": source_id}),
        ],
    )
    invalidate_queue_cache()
    return {
        "status": "success",
        "exception_id": eid,
        "meter_event_id": event_id,
        "sku_code": sku,
    }


def queue_metrics(*, use_cache: bool = True) -> dict[str, Any]:
    """Product metrics from ar_exceptions + HITL aggregate."""
    if use_cache:
        cached = DEFAULT_CACHE.get("ar:metrics:v1")
        if cached is not None:
            return cached

    from finance_ops.runtime.exception_queue import build_ar_exception_queue

    _ensure()
    from data_plane.warehouse import db

    snap = build_ar_exception_queue()
    rows = db.query_dicts("SELECT status, lane, amount FROM ar_exceptions")
    by_status: dict[str, int] = {}
    open_usd = 0.0
    for r in rows:
        st = str(r.get("status") or "")
        by_status[st] = by_status.get(st, 0) + 1
        if st in OPEN_STATUSES:
            open_usd += float(r.get("amount") or 0)
    billable = db.query_dicts(
        "SELECT COUNT(*) AS c, COALESCE(SUM(quantity),0) AS q "
        "FROM sku_meter_events WHERE status = 'billable'"
    )
    result = {
        "status": "success",
        "story": snap.get("story"),
        "projection": {
            "exception_count": len(rows),
            "by_status": by_status,
            "open_exception_usd": round(open_usd, 2),
            "billable_resolves": int((billable[0]["c"] if billable else 0) or 0),
        },
        "legacy_metrics": snap.get("metrics"),
        "cache": DEFAULT_CACHE.stats(),
        "needs_review": (by_status.get("open", 0) + by_status.get("pending_hitl", 0)) > 0,
    }
    if use_cache:
        DEFAULT_CACHE.set("ar:metrics:v1", result, METRICS_TTL)
    return result
