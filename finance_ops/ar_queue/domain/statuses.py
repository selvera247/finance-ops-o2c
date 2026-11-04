"""Exception lifecycle statuses (domain constants)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from finance_ops.copilot.types import Decision

# Active investigation / waiting-on-human statuses (included in status=open lists).
OPEN_STATUSES = frozenset(
    {
        "open",
        "pending_hitl",
        "escalated",
        "need_info",
        "ready_to_apply",
    }
)

# Copilot queue ranking includes these (investigation + ready guidance).
COPILOT_QUEUE_STATUSES = frozenset(
    {
        "open",
        "pending_hitl",
        "escalated",
        "need_info",
        "ready_to_apply",
    }
)

TERMINAL_STATUSES = frozenset({"resolved", "rejected", "closed_rejected"})

# Statuses that sync must not reopen back to "open".
PROTECTED_FROM_RESYNC = frozenset(
    {
        "resolved",
        "rejected",
        "closed_rejected",
        "ready_to_apply",
        "need_info",
        "escalated",
        "pending_hitl",
    }
)


def status_for_decision(decision: "Decision | str") -> str:
    """Map Copilot Decision enum → exception status."""
    value = decision.value if hasattr(decision, "value") else str(decision)
    mapping = {
        "accept": "ready_to_apply",
        "edit_ready_to_apply": "ready_to_apply",
        "reject": "closed_rejected",
        "escalate": "escalated",
        "need_info": "need_info",
    }
    return mapping.get(value, "open")
