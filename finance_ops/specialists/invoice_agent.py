from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from finance_ops.governance.callbacks import (
    after_agent_registry,
    before_agent_registry,
    before_tool_rbac,
)
from finance_ops.lib.config import default_model
from finance_ops.tools.feature_tools import lookup_customer_risk
from finance_ops.tools.hubspot_tools import (
    get_company,
    get_deal,
    get_deal_line_items,
    get_open_tickets_for_company,
    list_closed_won_deals,
)
from finance_ops.tools.invoice_tools import aging_summary, list_open_invoices, lookup_invoice

invoice_agent = Agent(
    model=default_model(),
    name="invoice_agent",
    description="Specialist for invoices, aging, and customer AR risk features.",
    instruction=(
        "Invoice specialist. Use tools for facts. Cite invoice_id and evidence_id. "
        "HubSpot read tools add customer context (owner, deals, tickets) for triage only — "
        "they must not change approval policy. Do not invent balances."
    ),
    tools=[
        lookup_invoice,
        list_open_invoices,
        aging_summary,
        lookup_customer_risk,
        get_company,
        get_deal,
        list_closed_won_deals,
        get_deal_line_items,
        get_open_tickets_for_company,
    ],
    before_tool_callback=before_tool_rbac,
    before_agent_callback=before_agent_registry,
    after_agent_callback=after_agent_registry,
)
