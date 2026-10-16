from __future__ import annotations

"""Unified read API for agents: fixtures | warehouse | bigquery."""

from typing import Any

from data_plane.config import data_mode
from finance_ops.lib import fixtures


def _warehouse_ready() -> bool:
    from data_plane.config import DUCKDB_PATH

    return DUCKDB_PATH.exists()


def list_invoices(
    *,
    customer_id: str | None = None,
    open_only: bool = False,
) -> list[dict[str, Any]]:
    mode = data_mode()
    if mode == "fixtures" or (mode == "warehouse" and not _warehouse_ready()):
        rows = fixtures.invoices()
        if customer_id:
            rows = [r for r in rows if r["customer_id"] == customer_id]
        if open_only:
            rows = [r for r in rows if r["status"] in {"open", "past_due"}]
        return rows

    if mode == "warehouse":
        from data_plane.warehouse import db

        sql = "SELECT * FROM invoices WHERE 1=1"
        params: list[Any] = []
        if customer_id:
            sql += " AND customer_id = ?"
            params.append(customer_id)
        if open_only:
            sql += " AND status IN ('open', 'past_due')"
        return db.query_dicts(sql, params)

    # bigquery path — fall back to warehouse/fixtures until client wired per-env
    from data_plane.warehouse.bq_adapter import bq_list_invoices

    return bq_list_invoices(customer_id=customer_id, open_only=open_only)


def get_invoice(invoice_id: str) -> dict[str, Any] | None:
    rows = [
        r
        for r in list_invoices()
        if str(r.get("invoice_id", "")).upper() == invoice_id.upper()
    ]
    return rows[0] if rows else None


def list_payments(
    *,
    customer_id: str | None = None,
    unmatched_only: bool = False,
) -> list[dict[str, Any]]:
    mode = data_mode()
    if mode == "fixtures" or (mode == "warehouse" and not _warehouse_ready()):
        rows = fixtures.payments()
        if customer_id:
            rows = [r for r in rows if r["customer_id"] == customer_id]
        if unmatched_only:
            rows = [r for r in rows if r["status"] in {"unmatched", "partial"}]
        return rows

    if mode == "warehouse":
        from data_plane.warehouse import db

        sql = "SELECT * FROM payments WHERE 1=1"
        params: list[Any] = []
        if customer_id:
            sql += " AND customer_id = ?"
            params.append(customer_id)
        if unmatched_only:
            sql += " AND status IN ('unmatched', 'partial')"
        return db.query_dicts(sql, params)

    from data_plane.warehouse.bq_adapter import bq_list_payments

    return bq_list_payments(customer_id=customer_id, unmatched_only=unmatched_only)


def get_payment(payment_id: str) -> dict[str, Any] | None:
    rows = [
        r
        for r in list_payments()
        if str(r.get("payment_id", "")).upper() == payment_id.upper()
    ]
    return rows[0] if rows else None


def list_contracts(*, customer_id: str | None = None, active_only: bool = True) -> list[dict[str, Any]]:
    mode = data_mode()
    if mode == "fixtures" or (mode == "warehouse" and not _warehouse_ready()):
        rows = fixtures.contracts()
        if customer_id:
            rows = [r for r in rows if r["customer_id"] == customer_id]
        if active_only:
            rows = [r for r in rows if r["status"] == "active"]
        return rows

    if mode == "warehouse":
        from data_plane.warehouse import db

        sql = "SELECT * FROM contracts WHERE 1=1"
        params: list[Any] = []
        if customer_id:
            sql += " AND customer_id = ?"
            params.append(customer_id)
        if active_only:
            sql += " AND status = 'active'"
        return db.query_dicts(sql, params)

    from data_plane.warehouse.bq_adapter import bq_list_contracts

    return bq_list_contracts(customer_id=customer_id, active_only=active_only)


def get_contract(contract_id: str) -> dict[str, Any] | None:
    rows = [
        r
        for r in list_contracts(active_only=False)
        if str(r.get("contract_id", "")).upper() == contract_id.upper()
    ]
    return rows[0] if rows else None


def knowledge_graph() -> dict[str, Any]:
    mode = data_mode()
    if mode == "fixtures" or (mode == "warehouse" and not _warehouse_ready()):
        return fixtures.knowledge_graph()

    from data_plane.warehouse import db

    nodes = db.query_dicts("SELECT id, type, label FROM kg_nodes")
    edges = db.query_dicts("SELECT source, target, type FROM kg_edges")
    return {"nodes": nodes, "edges": edges}


def customer_features(customer_id: str | None = None) -> list[dict[str, Any]]:
    if data_mode() == "fixtures" or not _warehouse_ready():
        return []
    from data_plane.warehouse import db

    if customer_id:
        return db.query_dicts(
            "SELECT * FROM customer_features WHERE customer_id = ?",
            [customer_id],
        )
    return db.query_dicts("SELECT * FROM customer_features")


def source_label() -> str:
    mode = data_mode()
    if mode == "warehouse" and _warehouse_ready():
        return "warehouse:duckdb"
    if mode == "bigquery":
        return "bigquery"
    return "fixture:json"
