from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from finance_ops.lib.config import default_model
from finance_ops.tools.graph_tools import get_entity, graph_neighborhood
from finance_ops.tools.payment_tools import suggest_payment_match
from finance_ops.tools.rag_tools import search_policies

reconciliation_agent = Agent(
    model=default_model(),
    name="reconciliation_agent",
    description=(
        "Specialist for reconciliation and multi-hop reasoning over the "
        "semantic knowledge graph (customers, contracts, invoices, payments, POs). "
        "Use for linking entities, exception investigation, and GraphRAG-style walks."
    ),
    instruction=(
        "You are the Reconciliation / Knowledge Graph specialist.\n"
        "- Use graph tools to relate customers, contracts, invoices, payments, and POs.\n"
        "- Use search_policies for matching/collections rules.\n"
        "- Use suggest_payment_match when investigating unmatched cash.\n"
        "- Explain the hop path (entity relationships) in plain language.\n"
        "- Cite entity ids and evidence_id; flag ambiguous cases for human review."
    ),
    tools=[get_entity, graph_neighborhood, search_policies, suggest_payment_match],
)
