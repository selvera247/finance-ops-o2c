"""Permission-scoped email evidence for Copilot match hypotheses.

Read-only. Never sends mail. Fail closed on cross-customer / unauthorized actor.
"""

from __future__ import annotations

from finance_ops.copilot.email_evidence.acl import (
    actor_may_access_customer,
    load_actor_acl,
)
from finance_ops.copilot.email_evidence.retrieve import (
    retrieve_email_evidence,
)
from finance_ops.copilot.email_evidence.types import EmailMessage

__all__ = [
    "EmailMessage",
    "actor_may_access_customer",
    "load_actor_acl",
    "retrieve_email_evidence",
]
