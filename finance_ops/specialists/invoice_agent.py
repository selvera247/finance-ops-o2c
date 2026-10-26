from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from finance_ops.governance.callbacks import (
    after_agent_registry,
    before_agent_registry,
    before_tool_rbac,
)
from finance_ops.lib.config import default_model
from finance_ops.tools.feature_tools import lookup_customer_risk
from finance_ops.tools.invoice_tools import aging_summary, list_open_invoices, lookup_invoice

invoice_agent = Agent(
    model=default_model(),
    name="invoice_agent",
    description="Specialist for invoices, aging, and customer AR risk features.",
    instruction=(
        "Invoice specialist. Use tools for facts. Cite invoice_id and evidence_id. "
        "Do not invent balances."
    ),
    tools=[lookup_invoice, list_open_invoices, aging_summary, lookup_customer_risk],
    before_tool_callback=before_tool_rbac,
    before_agent_callback=before_agent_registry,
    after_agent_callback=after_agent_registry,
)
