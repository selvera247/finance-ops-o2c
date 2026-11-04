"""Mailbox adapters — fixture filesystem (CI) + optional IMAP (env credentials).

Never sends email. Interface is read-only search by customer / payment hints.
"""

from __future__ import annotations

import email
import imaplib
import json
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from finance_ops.copilot.email_evidence.types import EmailMessage
from finance_ops.lib.paths import REPO_ROOT

_DEFAULT_FIXTURE = REPO_ROOT / "data" / "copilot" / "mailbox" / "messages.json"


class MailboxAdapter(ABC):
    """Read-only mailbox search interface."""

    name: str = "base"

    @abstractmethod
    def search(
        self,
        *,
        customer_id: str,
        payment_id: str | None = None,
        limit: int = 10,
    ) -> list[EmailMessage]:
        raise NotImplementedError


class FixtureMailboxAdapter(MailboxAdapter):
    """Filesystem / JSON fixture mailbox for CI and local demos."""

    name = "fixture"

    def __init__(self, path: Path | None = None) -> None:
        override = (os.getenv("COPILOT_MAILBOX_FIXTURE") or "").strip()
        self.path = Path(override) if override else (path or _DEFAULT_FIXTURE)
        self._cached_mtime: float | None = None
        self._cached_msgs: list[EmailMessage] | None = None

    def _load(self) -> list[EmailMessage]:
        if not self.path.is_file():
            self._cached_mtime = None
            self._cached_msgs = []
            return []
        mtime = self.path.stat().st_mtime
        if self._cached_msgs is not None and self._cached_mtime == mtime:
            return self._cached_msgs
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            self._cached_mtime = mtime
            self._cached_msgs = []
            return []
        out: list[EmailMessage] = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            out.append(
                EmailMessage(
                    message_id=str(row.get("message_id") or ""),
                    customer_id=str(row.get("customer_id") or ""),
                    thread_id=row.get("thread_id"),
                    subject=str(row.get("subject") or ""),
                    from_addr=row.get("from_addr"),
                    to_addrs=list(row.get("to_addrs") or []),
                    sent_at=row.get("sent_at"),
                    snippet=str(row.get("snippet") or ""),
                    body=str(row.get("body") or ""),
                    payment_refs=[str(x) for x in (row.get("payment_refs") or [])],
                    invoice_refs=[str(x) for x in (row.get("invoice_refs") or [])],
                    stub=False,
                    source="fixture",
                )
            )
        msgs = [m for m in out if m.message_id and m.customer_id]
        self._cached_mtime = mtime
        self._cached_msgs = msgs
        return msgs

    def search(
        self,
        *,
        customer_id: str,
        payment_id: str | None = None,
        limit: int = 10,
    ) -> list[EmailMessage]:
        want = customer_id.strip().upper()
        pay = (payment_id or "").strip().upper() or None
        messages = self._load()
        hits: list[EmailMessage] = []
        for msg in messages:
            if msg.customer_id.strip().upper() != want:
                continue
            if pay:
                refs = {r.strip().upper() for r in msg.payment_refs}
                blob = f"{msg.subject} {msg.snippet} {msg.body}".upper()
                if pay not in refs and pay not in blob:
                    # Still allow same-customer thread hits without payment id
                    # only when no payment filter match — prefer payment hits first.
                    continue
            hits.append(msg)
        if pay and not hits:
            # Fallback: same-customer messages (still ACL-filtered by caller).
            hits = [m for m in messages if m.customer_id.strip().upper() == want]
        return hits[: max(1, limit)]


class ImapMailboxAdapter(MailboxAdapter):
    """Optional IMAP shared-mailbox reader.

    Env:
      COPILOT_IMAP_HOST, COPILOT_IMAP_USER, COPILOT_IMAP_PASSWORD
      COPILOT_IMAP_FOLDER (default INBOX)
      COPILOT_IMAP_PORT (default 993)
    """

    name = "imap"

    def __init__(self) -> None:
        self.host = (os.getenv("COPILOT_IMAP_HOST") or "").strip()
        self.user = (os.getenv("COPILOT_IMAP_USER") or "").strip()
        self.password = (os.getenv("COPILOT_IMAP_PASSWORD") or "").strip()
        self.folder = (os.getenv("COPILOT_IMAP_FOLDER") or "INBOX").strip()
        port_raw = (os.getenv("COPILOT_IMAP_PORT") or "993").strip()
        try:
            self.port = int(port_raw)
        except ValueError:
            self.port = 993

    def configured(self) -> bool:
        return bool(self.host and self.user and self.password)

    def search(
        self,
        *,
        customer_id: str,
        payment_id: str | None = None,
        limit: int = 10,
    ) -> list[EmailMessage]:
        if not self.configured():
            return []
        query_bits = [customer_id]
        if payment_id:
            query_bits.append(payment_id)
        # IMAP TEXT search is coarse; ACL filter happens after parse.
        criteria = f'(OR SUBJECT "{customer_id}" TEXT "{customer_id}")'
        if payment_id:
            criteria = (
                f'(OR SUBJECT "{payment_id}" '
                f'(OR TEXT "{payment_id}" {criteria}))'
            )
        out: list[EmailMessage] = []
        try:
            client = imaplib.IMAP4_SSL(self.host, self.port)
            try:
                client.login(self.user, self.password)
                client.select(self.folder, readonly=True)
                typ, data = client.search(None, criteria)
                if typ != "OK" or not data or not data[0]:
                    return []
                ids = data[0].split()[-max(1, limit) :]
                for num in reversed(ids):
                    typ, msg_data = client.fetch(num, "(RFC822)")
                    if typ != "OK" or not msg_data or not msg_data[0]:
                        continue
                    raw = msg_data[0][1]
                    if not isinstance(raw, (bytes, bytearray)):
                        continue
                    parsed = email.message_from_bytes(bytes(raw))
                    body = _extract_body(parsed)
                    subject = str(parsed.get("Subject") or "")
                    msg_id = str(
                        parsed.get("Message-ID") or f"IMAP-{num.decode()}"
                    )
                    from_addr = str(parsed.get("From") or "")
                    # Heuristic customer tagging from body/subject — caller ACL
                    # still requires exact customer_id match on the message.
                    tagged = _guess_customer_id(body, subject, customer_id)
                    pay_refs = _find_refs(body + " " + subject, r"PAY-[\w-]+")
                    inv_refs = _find_refs(body + " " + subject, r"INV-[\w-]+")
                    out.append(
                        EmailMessage(
                            message_id=msg_id.strip(),
                            customer_id=tagged,
                            subject=subject,
                            from_addr=from_addr,
                            snippet=(body or "")[:180],
                            body=body or "",
                            payment_refs=pay_refs,
                            invoice_refs=inv_refs,
                            stub=False,
                            source="imap",
                        )
                    )
            finally:
                try:
                    client.logout()
                except Exception:
                    pass
        except Exception:
            return []
        # Keep only exact customer matches (fail closed before return).
        want = customer_id.strip().upper()
        return [m for m in out if m.customer_id.strip().upper() == want][:limit]


def _extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        parts: list[str] = []
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                payload = part.get_payload(decode=True)
                if isinstance(payload, (bytes, bytearray)):
                    parts.append(
                        payload.decode(part.get_content_charset() or "utf-8", "replace")
                    )
        return "\n".join(parts)
    payload = msg.get_payload(decode=True)
    if isinstance(payload, (bytes, bytearray)):
        return payload.decode(msg.get_content_charset() or "utf-8", "replace")
    return str(msg.get_payload() or "")


def _guess_customer_id(body: str, subject: str, fallback: str) -> str:
    blob = f"{subject}\n{body}"
    m = re.search(r"\b(C-\d+)\b", blob, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # If the searched customer_id appears, tag it; else leave empty → dropped.
    if fallback and fallback.upper() in blob.upper():
        return fallback.strip().upper()
    return ""


def _find_refs(text: str, pattern: str) -> list[str]:
    found = re.findall(pattern, text or "", flags=re.IGNORECASE)
    # preserve order, unique
    seen: set[str] = set()
    out: list[str] = []
    for item in found:
        key = item.upper()
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def get_mailbox_adapter() -> MailboxAdapter:
    """Prefer IMAP when credentials present; otherwise fixture mailbox."""
    backend = (os.getenv("COPILOT_MAILBOX_BACKEND") or "").strip().lower()
    if backend == "fixture":
        return FixtureMailboxAdapter()
    if backend == "imap":
        return ImapMailboxAdapter()
    imap = ImapMailboxAdapter()
    if imap.configured():
        return imap
    return FixtureMailboxAdapter()
