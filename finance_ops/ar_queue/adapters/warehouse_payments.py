"""Payment / invoice / portal catalog adapter over data_plane.repository."""

from __future__ import annotations

from typing import Any


class WarehousePaymentCatalog:
    def get_payment(self, payment_id: str) -> dict[str, Any] | None:
        from data_plane import repository as repo

        return repo.get_payment(payment_id)

    def list_payments(
        self, *, unmatched_only: bool = False
    ) -> list[dict[str, Any]]:
        from data_plane import repository as repo

        return repo.list_payments(unmatched_only=unmatched_only)

    def list_invoices(
        self,
        *,
        customer_id: str | None = None,
        open_only: bool = False,
    ) -> list[dict[str, Any]]:
        from data_plane import repository as repo

        return repo.list_invoices(customer_id=customer_id, open_only=open_only)

    def portal_extracts_by_external_id(self) -> dict[str, dict[str, Any]]:
        from data_plane import repository as repo

        return {
            str(r.get("external_id") or "").upper(): r for r in repo.portal_extracts()
        }


DEFAULT_PAYMENT_CATALOG = WarehousePaymentCatalog()
