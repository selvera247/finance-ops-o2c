"""Cash-Application Exception Copilot — guidance-only MVP shell.

North star product surface for the 10-week Copilot MVP. Conventional queue +
evidence + cited hypothesis + human decision → ApplyGuidancePacket.
Warehouse apply is demoted behind FINANCE_OPS_DEMO_APPLY.
"""

from __future__ import annotations

from finance_ops.copilot.config import (
    copilot_email_evidence_enabled,
    copilot_mode,
    demo_apply_enabled,
    digest_enabled,
    digest_send_enabled,
)
from finance_ops.copilot.types import (
    ApplyGuidancePacket,
    Case,
    Citation,
    Decision,
    EvidencePack,
    InvestigationSummary,
    MatchHypothesis,
    MatchLine,
)

__all__ = [
    "ApplyGuidancePacket",
    "Case",
    "Citation",
    "Decision",
    "EvidencePack",
    "InvestigationSummary",
    "MatchHypothesis",
    "MatchLine",
    "copilot_email_evidence_enabled",
    "copilot_mode",
    "demo_apply_enabled",
    "digest_enabled",
    "digest_send_enabled",
]
