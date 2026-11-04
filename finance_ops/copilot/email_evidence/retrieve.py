"""Retrieve ACL-filtered email evidence items for a Copilot case."""

from __future__ import annotations

from typing import Any

from finance_ops.copilot.email_evidence.acl import (
    actor_may_access_customer,
    filter_messages_for_customer,
)
from finance_ops.copilot.email_evidence.adapters import (
    MailboxAdapter,
    get_mailbox_adapter,
)
from finance_ops.copilot.email_evidence.types import EmailMessage
from finance_ops.copilot.types import EvidenceItem


class EmailAccessDenied(PermissionError):
    """Raised when actor cannot access the case customer mailbox scope."""


def retrieve_email_messages(
    *,
    customer_id: str,
    payment_id: str | None = None,
    actor: str | None = None,
    adapter: MailboxAdapter | None = None,
    limit: int = 5,
    fail_closed: bool = True,
) -> dict[str, Any]:
    """Search mailbox under permission filters.

    Returns dict with messages + denial metadata. Never returns cross-customer
    messages. When actor is unauthorized, returns empty messages and
    ``access_denied=True`` (fail closed).
    """
    customer_id = (customer_id or "").strip()
    if not customer_id:
        return {
            "status": "error",
            "error": "customer_id_required",
            "messages": [],
            "access_denied": True,
            "adapter": None,
        }

    if not actor_may_access_customer(actor, customer_id):
        return {
            "status": "denied",
            "error": "actor_not_authorized_for_customer",
            "customer_id": customer_id,
            "actor": actor,
            "messages": [],
            "access_denied": True,
            "adapter": None,
        }

    box = adapter or get_mailbox_adapter()
    raw = box.search(
        customer_id=customer_id,
        payment_id=payment_id,
        limit=limit * 3,  # over-fetch then ACL filter
    )
    # Absolute fail-closed: drop any mismatched customer_id.
    filtered = filter_messages_for_customer(raw, customer_id=customer_id)
    # Defense in depth: never leak another customer's payment_refs alone.
    safe: list[EmailMessage] = []
    for msg in filtered:
        if msg.customer_id.strip().upper() != customer_id.strip().upper():
            if fail_closed:
                continue
        safe.append(msg)
    safe = safe[:limit]
    return {
        "status": "success",
        "customer_id": customer_id,
        "actor": actor,
        "adapter": getattr(box, "name", "unknown"),
        "messages": safe,
        "access_denied": False,
        "dropped_cross_customer": max(0, len(raw) - len(filtered)),
    }


def retrieve_email_evidence(
    *,
    customer_id: str,
    payment_id: str | None = None,
    actor: str | None = None,
    adapter: MailboxAdapter | None = None,
    limit: int = 5,
) -> list[EvidenceItem]:
    """Build EvidenceItem list for the evidence pack (empty on deny)."""
    result = retrieve_email_messages(
        customer_id=customer_id,
        payment_id=payment_id,
        actor=actor,
        adapter=adapter,
        limit=limit,
    )
    if result.get("access_denied") or result.get("status") != "success":
        return []
    items: list[EvidenceItem] = []
    for msg in result["messages"]:
        assert isinstance(msg, EmailMessage)
        items.append(
            EvidenceItem(
                source_id=msg.message_id,
                source_type="email",
                label=f"Email: {msg.subject or msg.message_id}",
                fields=msg.to_evidence_fields(),
                stub=False,
            )
        )
    return items
