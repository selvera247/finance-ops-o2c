"""Prototype mode flags for Copilot MVP demos (modes A–D) + digest/email/OCR."""

from __future__ import annotations

import os
from typing import Literal

CopilotMode = Literal["workbench", "slack_contrast", "rules_only"]

_VALID_MODES = frozenset({"workbench", "slack_contrast", "rules_only"})
_VALID_BANDS = frozenset({"high", "medium", "low", "insufficient"})


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
    """When true, evidence pack includes ACL-filtered email artifacts (A3 gated)."""
    return _truthy("COPILOT_EMAIL_EVIDENCE")


def demo_apply_enabled() -> bool:
    """Quarantine warehouse apply — Copilot happy path never applies unless set."""
    return _truthy("FINANCE_OPS_DEMO_APPLY")


def auto_allow_blocked_on_copilot() -> bool:
    """Copilot path never honors auto_allow / silent apply."""
    return True


def remittance_pdf_extract_enabled() -> bool:
    """Prefer file/PDF remittance extract over bank-reference-only text.

    On by default when fixtures exist; set COPILOT_REMITTANCE_EXTRACT=0 to disable.
    """
    raw = os.getenv("COPILOT_REMITTANCE_EXTRACT")
    if raw is None or raw.strip() == "":
        return True
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def digest_enabled() -> bool:
    """Optional daily/queued digest — **off by default** (alert fatigue)."""
    return _truthy("COPILOT_DIGEST_ENABLED")


def digest_send_enabled() -> bool:
    """Second gate: stub Slack/email delivery intent. Off by default."""
    return _truthy("COPILOT_DIGEST_SEND")


def digest_min_confidence() -> str:
    """Minimum confidence_band to include in digest (default medium)."""
    raw = (os.getenv("COPILOT_DIGEST_MIN_CONFIDENCE") or "medium").strip().lower()
    if raw not in _VALID_BANDS:
        return "medium"
    return raw


def digest_exclude_insufficient() -> bool:
    """Drop insufficient-data cases from digest (default on)."""
    raw = os.getenv("COPILOT_DIGEST_EXCLUDE_INSUFFICIENT")
    if raw is None or raw.strip() == "":
        return True
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def digest_max_items() -> int:
    try:
        return max(1, int((os.getenv("COPILOT_DIGEST_MAX_ITEMS") or "25").strip()))
    except ValueError:
        return 25


def prototype_mode_label() -> str:
    """Human label for demo modes A–D (meeting plan)."""
    mode = copilot_mode()
    email = copilot_email_evidence_enabled()
    if mode == "workbench" and not email:
        return "A"  # workbench, ERP+remittance only
    if mode == "workbench" and email:
        return "B"  # workbench + email evidence
    if mode == "slack_contrast":
        return "C"  # Slack HITL contrast (not primary UX)
    return "D"  # rules_only — no LLM draft
