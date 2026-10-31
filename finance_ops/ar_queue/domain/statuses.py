"""Exception lifecycle statuses (domain constants)."""

from __future__ import annotations

OPEN_STATUSES = frozenset({"open", "pending_hitl", "escalated"})
TERMINAL_STATUSES = frozenset({"resolved", "rejected"})
