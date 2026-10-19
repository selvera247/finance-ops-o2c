from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from finance_ops.lib.config import default_model
from finance_ops.tools.contract_tools import lookup_contract, lookup_customer_contract

contracts_agent = Agent(
    model=default_model(),
    name="contracts_agent",
    description="Specialist for contract terms, credit limits, and SLA notes.",
    instruction="Contracts specialist. Quote payment_terms and cite contract_id + evidence_id.",
    tools=[lookup_contract, lookup_customer_contract],
)
