"""Cash-Application Exception Copilot eval scoreboard (Weeks 5–6).

Primary metrics (discovery §8 / repurpose §3.4):
  - citation_validity
  - harmful_error_rate
  - insufficient_data_calibration

Trajectory evals under evals/ remain the RBAC / no-silent-apply regression gate.
"""

from __future__ import annotations

from evals.copilot.checkers import (
    CaseCheckResult,
    Scoreboard,
    check_case,
    summarize_scoreboard,
)
from evals.copilot.gold import GoldCase, load_gold_cases

__all__ = [
    "CaseCheckResult",
    "GoldCase",
    "Scoreboard",
    "check_case",
    "load_gold_cases",
    "summarize_scoreboard",
]
