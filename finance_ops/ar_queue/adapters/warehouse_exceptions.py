"""DuckDB adapter for ar_exceptions + sku_meter_events."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from finance_ops.ar_queue.domain.skus import sku_for_lane
from finance_ops.ar_queue.domain.statuses import (
    OPEN_STATUSES,
    PROTECTED_FROM_RESYNC,
    TERMINAL_STATUSES,
)


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


def clean_exception_row(row: dict[str, Any]) -> dict[str, Any]:
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


class WarehouseExceptionStore:
    def ensure_schema(self) -> None:
        from data_plane.warehouse import db

        db.init_schema()

    def get_existing(self, exception_ids: list[str]) -> dict[str, dict[str, Any]]:
        from data_plane.warehouse import db

        existing_map: dict[str, dict[str, Any]] = {}
        if not exception_ids:
            return existing_map
        with db.connection() as con:
            for i in range(0, len(exception_ids), 200):
                chunk = exception_ids[i : i + 200]
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
        return existing_map

    def replace_row(
        self,
        row: dict[str, Any],
        *,
        opened_at: Any,
        now: datetime,
    ) -> None:
        from data_plane.warehouse import db

        # DELETE+INSERT must share one connection/lock — otherwise concurrent
        # GET /cases can 404 mid-replace (sibling of DuckDB connect races).
        eid = row["exception_id"]
        with db.connection() as con:
            con.execute("DELETE FROM ar_exceptions WHERE exception_id = ?", [eid])
            con.execute(
                "INSERT INTO ar_exceptions VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                _row_params(row, opened_at=opened_at, now=now),
            )

    def replace_rows_batch(
        self,
        rows: list[tuple[dict[str, Any], Any]],
        *,
        now: datetime,
    ) -> None:
        from data_plane.warehouse import db

        with db.connection() as con:
            for row, opened_at in rows:
                eid = row["exception_id"]
                con.execute("DELETE FROM ar_exceptions WHERE exception_id = ?", [eid])
                con.execute(
                    "INSERT INTO ar_exceptions VALUES "
                    "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    _row_params(row, opened_at=opened_at, now=now),
                )

    def fetch_by_id(self, exception_id: str) -> dict[str, Any] | None:
        from data_plane.warehouse import db

        rows = db.query_dicts(
            "SELECT * FROM ar_exceptions WHERE exception_id = ?",
            [exception_id.strip()],
        )
        return clean_exception_row(rows[0]) if rows else None

    def list_rows(
        self,
        *,
        status: str | None,
        lane: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        from data_plane.warehouse import db

        sql = "SELECT * FROM ar_exceptions WHERE 1=1"
        params: list[Any] = []
        if status:
            if status == "open":
                placeholders = ",".join("?" * len(OPEN_STATUSES))
                sql += f" AND status IN ({placeholders})"
                params.extend(sorted(OPEN_STATUSES))
            else:
                sql += " AND status = ?"
                params.append(status)
        if lane:
            sql += " AND lane = ?"
            params.append(lane)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        return [clean_exception_row(r) for r in db.query_dicts(sql, params)]

    def list_status_amounts(self) -> list[dict[str, Any]]:
        from data_plane.warehouse import db

        return db.query_dicts("SELECT status, lane, amount FROM ar_exceptions")

    def count_billable_resolves(self) -> int:
        from data_plane.warehouse import db

        billable = db.query_dicts(
            "SELECT COUNT(*) AS c, COALESCE(SUM(quantity),0) AS q "
            "FROM sku_meter_events WHERE status = 'billable'"
        )
        return int((billable[0]["c"] if billable else 0) or 0)

    def insert_meter_event(
        self,
        *,
        event_id: str,
        sku: str,
        exception_id: str,
        customer_id: Any,
        now: datetime,
        meta: dict[str, Any],
    ) -> None:
        from data_plane.warehouse import db

        with db.connection() as con:
            con.execute("DELETE FROM sku_meter_events WHERE event_id = ?", [event_id])
            con.execute(
                "INSERT INTO sku_meter_events VALUES (?,?,?,?,?,?,?,?,?)",
                [
                    event_id,
                    sku,
                    exception_id,
                    customer_id,
                    1.0,
                    "exception",
                    "billable",
                    now,
                    json.dumps(meta),
                ],
            )


def preserve_terminal_status(
    row: dict[str, Any],
    prev: dict[str, Any] | None,
) -> dict[str, Any]:
    """Do not reopen terminal or Copilot in-progress statuses on sync."""
    if not prev:
        return row
    prev_status = str(prev.get("status") or "")
    if prev_status in PROTECTED_FROM_RESYNC or prev_status in TERMINAL_STATUSES:
        if row.get("status") in OPEN_STATUSES or row.get("status") == "open":
            return {**row, "status": prev_status}
    return row


DEFAULT_EXCEPTION_STORE = WarehouseExceptionStore()
