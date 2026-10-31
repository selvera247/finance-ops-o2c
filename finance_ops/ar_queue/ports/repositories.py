"""Ports (interfaces) for AR queue persistence and catalogs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ExceptionStore(Protocol):
    """Persistence for ar_exceptions + sku_meter_events."""

    def ensure_schema(self) -> None: ...

    def get_existing(
        self, exception_ids: list[str]
    ) -> dict[str, dict[str, Any]]: ...

    def replace_row(
        self,
        row: dict[str, Any],
        *,
        opened_at: Any,
        now: datetime,
    ) -> None: ...

    def replace_rows_batch(
        self,
        rows: list[tuple[dict[str, Any], Any]],
        *,
        now: datetime,
    ) -> None:
        """Each item is (row_dict, opened_at)."""
        ...

    def fetch_by_id(self, exception_id: str) -> dict[str, Any] | None: ...

    def list_rows(
        self,
        *,
        status: str | None,
        lane: str | None,
        limit: int,
    ) -> list[dict[str, Any]]: ...

    def list_status_amounts(self) -> list[dict[str, Any]]: ...

    def count_billable_resolves(self) -> int: ...

    def insert_meter_event(
        self,
        *,
        event_id: str,
        sku: str,
        exception_id: str,
        customer_id: Any,
        now: datetime,
        meta: dict[str, Any],
    ) -> None: ...


@runtime_checkable
class PaymentCatalog(Protocol):
    """Read model for payments / invoices / portal extracts."""

    def get_payment(self, payment_id: str) -> dict[str, Any] | None: ...

    def list_payments(
        self, *, unmatched_only: bool = False
    ) -> list[dict[str, Any]]: ...

    def list_invoices(
        self,
        *,
        customer_id: str | None = None,
        open_only: bool = False,
    ) -> list[dict[str, Any]]: ...

    def portal_extracts_by_external_id(self) -> dict[str, dict[str, Any]]: ...


@runtime_checkable
class CachePort(Protocol):
    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any, ttl_seconds: float) -> None: ...

    def invalidate_prefix(self, prefix: str) -> int: ...

    def stats(self) -> dict[str, Any]: ...
