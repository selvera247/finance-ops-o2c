"""Reason codes required on Reject / Escalate / Need-info (eval fuel)."""

from __future__ import annotations

from finance_ops.copilot.types import Decision

REASON_CODES: dict[str, frozenset[str]] = {
    Decision.reject.value: frozenset(
        {
            "reject_wrong_customer",
            "reject_duplicate",
            "reject_not_our_payment",
            "reject_other",
        }
    ),
    Decision.escalate.value: frozenset(
        {
            "escalate_materiality",
            "escalate_ambiguous",
            "escalate_policy",
            "escalate_other",
        }
    ),
    Decision.need_info.value: frozenset(
        {
            "need_info_remittance",
            "need_info_email",
            "need_info_invoice",
            "need_info_other",
        }
    ),
}

REQUIRES_REASON = frozenset(
    {
        Decision.reject.value,
        Decision.escalate.value,
        Decision.need_info.value,
    }
)


def validate_reason_code(decision: Decision | str, reason_code: str | None) -> str | None:
    """Return error message if reason is missing/invalid; else None."""
    dec = decision.value if isinstance(decision, Decision) else str(decision)
    if dec not in REQUIRES_REASON:
        return None
    if not reason_code or not str(reason_code).strip():
        return f"reason_code required for decision={dec}"
    code = str(reason_code).strip().lower()
    allowed = REASON_CODES.get(dec, frozenset())
    if code not in allowed:
        return f"invalid reason_code={code} for decision={dec}; allowed={sorted(allowed)}"
    return None
