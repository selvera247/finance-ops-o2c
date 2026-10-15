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
    description=(
        "Specialist for payment lookup, unmatched cash, and cash-application "
        "match suggestions. Use for remittances, partial pays, and exceptions."
    ),
    instruction=(
        "You are the Payments / Cash Application specialist.\n"
        "- Use tools before recommending any match.\n"
        "- Treat match suggestions as proposals that need_review unless "
        "already matched in source data.\n"
        "- Cite payment_id, candidate invoice_id, score/reasons, and evidence_id.\n"
        "- Never auto-write-off amounts; flag for human review instead."
    ),
    tools=[lookup_payment, list_unmatched_payments, suggest_payment_match],
)
