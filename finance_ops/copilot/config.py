"""Prototype mode flags for Copilot MVP demos (modes A–D)."""

from __future__ import annotations

import os
from typing import Literal

CopilotMode = Literal["workbench", "slack_contrast", "rules_only"]

_VALID_MODES = frozenset({"workbench", "slack_contrast", "rules_only"})


def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def copilot_mode() -> CopilotMode:
    """Product demo mode.

    - workbench (default): Copilot UI/API is source of truth for decisions
    - slack_contrast: Slack HITL Approve/Reject path for contrast demos only
    - rules_only: deterministic match candidates; skip LLM draft path
    """
    raw = (os.getenv("COPILOT_MODE") or "workbench").strip().lower()
    if raw not in _VALID_MODES:
        return "workbench"
    return raw  # type: ignore[return-value]


def copilot_email_evidence_enabled() -> bool:
    """When true, evidence pack includes stubbed email artifacts (A3 gated)."""
    return _truthy("COPILOT_EMAIL_EVIDENCE")


def demo_apply_enabled() -> bool:
    """Quarantine warehouse apply — Copilot happy path never applies unless set."""
    return _truthy("FINANCE_OPS_DEMO_APPLY")


def auto_allow_blocked_on_copilot() -> bool:
    """Copilot path never honors auto_allow / silent apply."""
    return True


def prototype_mode_label() -> str:
    """Human label for demo modes A–D (meeting plan)."""
    mode = copilot_mode()
    email = copilot_email_evidence_enabled()
    if mode == "workbench" and not email:
        return "A"  # workbench, ERP+remittance only
    if mode == "workbench" and email:
        return "B"  # workbench + email evidence stub
    if mode == "slack_contrast":
        return "C"  # Slack HITL contrast (not primary UX)
    return "D"  # rules_only — no LLM draft
