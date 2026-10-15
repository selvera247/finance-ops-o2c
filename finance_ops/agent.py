from __future__ import annotations

"""Finance Ops multi-agent system (ADK).

Root coordinator delegates to invoice, payments, contracts, and reconciliation
specialists. Local JSON fixtures power tools until BigQuery / Vector Search
are wired.
"""

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
from finance_ops.tools.rag_tools import search_policies

root_agent = Agent(
    model=default_model(),
    name="finance_ops_coordinator",
    description=(
        "Finance operations coordinator for AR collections, cash application, "
        "contract terms, and knowledge-graph reconciliation with evidence/governance."
    ),
    instruction=(
        "You are the Finance Ops coordinator for a customer-facing Data-to-AI demo.\n"
        "\n"
        "Routing:\n"
        "- Invoice status, open AR, aging → invoice_agent\n"
        "- Payments, unmatched cash, match suggestions → payments_agent\n"
        "- Payment terms, credit limits, SLA notes → contracts_agent\n"
        "- Multi-entity links, exceptions, GraphRAG walks → reconciliation_agent\n"
        "\n"
        "Governance:\n"
        "- Prefer tool-backed facts. Cite ids (invoice_id, payment_id, contract_id) "
        "and evidence_id in every substantive answer.\n"
        "- Use search_policies for policy grounding before recommending actions.\n"
        "- Use flag_for_human_review for write-offs, legal escalation, or low-confidence matches.\n"
        "- Use get_evidence / recent_evidence when asked about audit trails.\n"
        "- If BigQuery mode is discussed, call bigquery_status.\n"
        "\n"
        "Style:\n"
        "- Be concise and analyst-grade.\n"
        "- Separate Recommended action vs Evidence.\n"
        "- Never invent balances or contractual terms."
    ),
    tools=[
        search_policies,
        flag_for_human_review,
        get_evidence,
        recent_evidence,
        bigquery_status,
    ],
    sub_agents=[
        invoice_agent,
        payments_agent,
        contracts_agent,
        reconciliation_agent,
    ],
)
