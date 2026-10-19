from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from finance_ops.lib.config import default_model
from finance_ops.specialists import (
    contracts_agent,
    invoice_agent,
    payments_agent,
    reconciliation_agent,
)
from finance_ops.tools.bigquery_tools import bigquery_status
from finance_ops.tools.governance_tools import (
    flag_for_human_review,
    get_evidence,
    recent_evidence,
)
from finance_ops.tools.gui_tools import (
    fetch_legacy_bank_statement,
    list_bank_statements,
    list_portal_extracts,
    process_portal_incoming,
)
from finance_ops.tools.rag_tools import search_policies

root_agent = Agent(
    model=default_model(),
    name="finance_ops_coordinator",
    description=(
        "Finance operations coordinator for AR, cash app, contracts, graph reconciliation, "
        "and multi-portal GUI extracts (bank / SageSure-like / payer drop zones) with evidence."
    ),
    instruction=(
        "You are the Finance Ops coordinator.\n"
        "Routing: invoices/aging/risk → invoice_agent; payments → payments_agent; "
        "contracts → contracts_agent; graph links → reconciliation_agent.\n"
        "Portal extract flow:\n"
        "- fetch_legacy_bank_statement for the mock bank GUI pull\n"
        "- process_portal_incoming to drain data/incoming/<portal_id>/\n"
        "- list_portal_extracts (or list_bank_statements) to inspect ingested rows\n"
        "Always cite evidence_id. For write-offs say needs_review and flag_for_human_review.\n"
        "Never invent balances."
    ),
    tools=[
        search_policies,
        flag_for_human_review,
        get_evidence,
        recent_evidence,
        bigquery_status,
        fetch_legacy_bank_statement,
        process_portal_incoming,
        list_portal_extracts,
        list_bank_statements,
    ],
    sub_agents=[invoice_agent, payments_agent, contracts_agent, reconciliation_agent],
)
