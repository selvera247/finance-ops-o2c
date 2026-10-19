from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from finance_ops.lib.config import default_model
from finance_ops.tools.payment_tools import (
    list_unmatched_payments,
    lookup_payment,
    suggest_payment_match,
)

payments_agent = Agent(
    model=default_model(),
    name="payments_agent",
    description="Specialist for payments, unmatched cash, and match suggestions.",
    instruction=(
        "Payments specialist. Treat matches as needs_review unless already matched. "
        "Cite payment_id and evidence_id."
    ),
    tools=[lookup_payment, list_unmatched_payments, suggest_payment_match],
)
