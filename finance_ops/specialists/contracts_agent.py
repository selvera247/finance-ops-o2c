from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from finance_ops.lib.config import default_model
from finance_ops.tools.contract_tools import lookup_contract, lookup_customer_contract

contracts_agent = Agent(
    model=default_model(),
    name="contracts_agent",
    description=(
        "Specialist for contract terms, payment terms, credit limits, and SLA "
        "notes. Use when collections or disputes depend on contractual rules."
    ),
    instruction=(
        "You are the Contracts specialist.\n"
        "- Retrieve contract records via tools before stating terms.\n"
        "- Quote payment_terms, credit_limit, and sla_notes when relevant.\n"
        "- Cite contract_id and evidence_id.\n"
        "- If multiple contracts exist, list them and ask which applies."
    ),
    tools=[lookup_contract, lookup_customer_contract],
)
