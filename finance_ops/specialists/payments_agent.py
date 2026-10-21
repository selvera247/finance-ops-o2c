from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from finance_ops.lib.config import default_model
from finance_ops.tools.payment_tools import (
    apply_payment_match,
    list_unmatched_payments,
    lookup_payment,
    request_cash_app_approval,
    suggest_payment_match,
)
from finance_ops.tools.sandbox_tools import run_sandboxed_calc, run_sandboxed_python

payments_agent = Agent(
    model=default_model(),
    name="payments_agent",
    description="Specialist for payments, unmatched cash, match suggestions, and HITL apply.",
    instruction=(
        "Payments specialist. Treat matches as needs_review unless already matched. "
        "For cash app: suggest_payment_match then request_cash_app_approval "
        "(Slack/HITL); do not call apply_payment_match unless ops explicitly bypasses HITL. "
        "For amount tolerances / remittance math use run_sandboxed_calc or run_sandboxed_python "
        "(returns numbers only — never applies matches). "
        "Cite payment_id and evidence_id."
    ),
    tools=[
        lookup_payment,
        list_unmatched_payments,
        suggest_payment_match,
        request_cash_app_approval,
        apply_payment_match,
        run_sandboxed_calc,
        run_sandboxed_python,
    ],
)
