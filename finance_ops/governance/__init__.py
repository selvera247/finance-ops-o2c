"""Code-enforced governance: RBAC, audit, policy-as-code (+ registry in D3)."""

from __future__ import annotations

from finance_ops.governance.callbacks import after_agent_lifecycle_stub, before_tool_rbac
from finance_ops.governance.policy import Decision, requires_approval
from finance_ops.governance.rbac import allowed_tools_for, is_tool_allowed

__all__ = [
    "Decision",
    "allowed_tools_for",
    "before_tool_rbac",
    "after_agent_lifecycle_stub",
    "is_tool_allowed",
    "requires_approval",
]
