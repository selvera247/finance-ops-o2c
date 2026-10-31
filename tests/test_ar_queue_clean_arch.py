"""Clean-architecture invariants for the AR queue bounded context."""

from __future__ import annotations

import ast
from pathlib import Path

from finance_ops.ar_queue.domain.ids import exception_id
from finance_ops.ar_queue.domain.matching import score_against_invoices
from finance_ops.ar_queue.domain.portal_classify import classify_portal_row
from finance_ops.ar_queue.domain.skus import sku_for_lane


DOMAIN_ROOT = Path(__file__).resolve().parents[1] / "finance_ops" / "ar_queue" / "domain"
FORBIDDEN_IMPORT_ROOTS = (
    "data_plane",
    "finance_ops.runtime",
    "finance_ops.tools",
    "finance_ops.services",
    "finance_ops.adapters",
    "finance_ops.ar_queue.adapters",
    "finance_ops.ar_queue.application",
)


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_domain_has_no_infrastructure_imports() -> None:
    for py in DOMAIN_ROOT.glob("*.py"):
        if py.name == "__init__.py":
            continue
        for mod in _imported_modules(py):
            assert not any(
                mod == root or mod.startswith(root + ".")
                for root in FORBIDDEN_IMPORT_ROOTS
            ), f"{py.name} imports infrastructure: {mod}"


def test_domain_scoring_pure() -> None:
    payment = {
        "payment_id": "PAY-X",
        "customer_id": "C1",
        "amount": 100.0,
        "reference": "INV-1 PO-9",
        "currency": "USD",
    }
    invoices = [
        {
            "invoice_id": "INV-1",
            "po_number": "PO-9",
            "amount": 100.0,
            "status": "open",
        }
    ]
    out = score_against_invoices(payment, invoices)
    assert out["status"] == "success"
    assert out["recommendation"] == "INV-1"
    assert out["candidates"][0]["score"] >= 1.0


def test_domain_portal_and_ids() -> None:
    denied = classify_portal_row(
        "CLM-1",
        {"status": "denied", "description": "no", "amount": 10},
    )
    assert denied["disposition"] == "escalate_appeal"
    assert exception_id("cash_app", "pay-1") == "EXE-cash_app-PAY-1"
    assert sku_for_lane("portal_remittance") == "resolve.portal"


def test_facade_exports_match_package() -> None:
    from finance_ops import ar_queue
    from finance_ops.services import queue_service, sku_catalog

    assert queue_service.sync_from_warehouse is ar_queue.sync_from_warehouse
    assert queue_service.list_exceptions is ar_queue.list_exceptions
    assert sku_catalog.list_skus is ar_queue.list_skus
