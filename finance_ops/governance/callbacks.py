"""ADK callbacks for governance (RBAC today; lifecycle hook stub for D3)."""

from __future__ import annotations

from typing import Any, Optional

from finance_ops.governance.audit import append_audit
from finance_ops.governance.rbac import is_tool_allowed


def _tool_name(tool: Any) -> str:
    name = getattr(tool, "name", None) or getattr(tool, "__name__", None)
    return str(name or "").strip()


def before_tool_rbac(
    tool: Any,
    args: dict[str, Any],
    tool_context: Any,
) -> Optional[dict[str, Any]]:
    """Deny tools not on the agent allowlist. Non-None return skips the tool call."""
    agent = str(getattr(tool_context, "agent_name", "") or "").strip()
    tool_name = _tool_name(tool)
    try:
        allowed, reason = is_tool_allowed(agent, tool_name)
    except Exception as exc:  # noqa: BLE001 — fail closed
        allowed, reason = False, f"rbac_error:{exc}"

    if allowed:
        append_audit(
            event="tool_rbac",
            agent=agent or "unknown",
            tool=tool_name or "unknown",
            args=args if isinstance(args, dict) else {},
            decision="allow",
            reason=reason,
        )
        return None

    append_audit(
        event="tool_rbac",
        agent=agent or "unknown",
        tool=tool_name or "unknown",
        args=args if isinstance(args, dict) else {},
        decision="deny",
        reason=reason,
    )
    return {
        "status": "denied",
        "error": "rbac_denied",
        "agent": agent,
        "tool": tool_name,
        "reason": reason,
        "needs_review": True,
    }


def after_agent_lifecycle_stub(callback_context: Any) -> Optional[Any]:
    """Placeholder for D3 registry last_run_at updates — no-op for D1."""
    _ = callback_context
    return None
