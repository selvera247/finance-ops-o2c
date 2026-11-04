"""Email evidence message shape."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EmailMessage(BaseModel):
    message_id: str
    customer_id: str
    thread_id: str | None = None
    subject: str = ""
    from_addr: str | None = None
    to_addrs: list[str] = Field(default_factory=list)
    sent_at: str | None = None
    snippet: str = ""
    body: str = ""
    payment_refs: list[str] = Field(default_factory=list)
    invoice_refs: list[str] = Field(default_factory=list)
    stub: bool = False
    source: str = "fixture"  # fixture | imap

    def to_evidence_fields(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "customer_id": self.customer_id,
            "thread_id": self.thread_id,
            "subject": self.subject,
            "from_addr": self.from_addr,
            "to_addrs": list(self.to_addrs),
            "sent_at": self.sent_at,
            "snippet": self.snippet,
            "body_preview": (self.body or "")[:500],
            "payment_refs": list(self.payment_refs),
            "invoice_refs": list(self.invoice_refs),
            "source": self.source,
        }
