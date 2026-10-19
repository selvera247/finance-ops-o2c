from __future__ import annotations

from google.adk.agents.llm_agent import Agent

from finance_ops.lib.config import default_model
from finance_ops.tools.graph_tools import get_entity, graph_neighborhood
from finance_ops.tools.payment_tools import suggest_payment_match
from finance_ops.tools.rag_tools import search_policies

reconciliation_agent = Agent(
    model=default_model(),
    name="reconciliation_agent",
    description="Specialist for knowledge-graph reconciliation and GraphRAG walks.",
    instruction="Explain entity hop paths. Cite ids and evidence_id. Flag ambiguity for review.",
    tools=[get_entity, graph_neighborhood, search_policies, suggest_payment_match],
)
