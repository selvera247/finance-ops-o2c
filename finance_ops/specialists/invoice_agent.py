from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from finance_ops.lib.config import default_model
from finance_ops.tools.feature_tools import lookup_customer_risk
from finance_ops.tools.invoice_tools import (
    aging_summary,
    list_open_invoices,
    lookup_invoice,
)

invoice_agent = Agent(
    model=default_model(),
    name="invoice_agent",
    description=(
        "Specialist for invoice lookup, open AR lists, aging summaries, and "
        "customer AR risk features. Use for invoice status, balances, aging, risk."
    ),
    instruction=(
        "You are the Invoice specialist for a finance operations desk.\n"
        "- Use tools for every factual claim about invoices, aging, or risk features.\n"
        "- Always cite invoice_id and evidence_id from tool results.\n"
        "- If data is missing, say so and set needs_review rather than guessing.\n"
        "- Do not invent payments or contract terms; escalate those domains."
    ),
    tools=[lookup_invoice, list_open_invoices, aging_summary, lookup_customer_risk],
)
