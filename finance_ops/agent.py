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
from finance_ops.tools.runtime_tools import (
    circuit_status,
    decide_approval,
    get_workflow_status,
    list_pending_approvals,
    request_approval,
    reset_circuit_breaker,
    resolve_portal_with_fallback,
    resume_durable_workflow,
    run_typed_a2a_aging,
    start_durable_reconcile,
)

root_agent = Agent(
    model=default_model(),
    name="finance_ops_coordinator",
    description=(
        "Finance operations coordinator for AR, cash app, contracts, graph reconciliation, "
        "multi-portal GUI extracts, HITL approvals, durable reconcile, and typed A2A handoffs."
    ),
    instruction=(
        "You are the Finance Ops coordinator.\n"
        "Routing: invoices/aging/risk → invoice_agent; payments → payments_agent; "
        "contracts → contracts_agent; graph links → reconciliation_agent.\n"
        "Portal extract flow:\n"
        "- Prefer resolve_portal_with_fallback (warehouse/API first, browser on miss)\n"
        "- fetch_legacy_bank_statement for forced GUI pull\n"
        "- process_portal_incoming to drain data/incoming/<portal_id>/\n"
        "- list_portal_extracts (or list_bank_statements) to inspect ingested rows\n"
        "HITL: request_approval / flag_for_human_review(create_approval=true); "
        "resume with decide_approval after human decides.\n"
        "Durable: start_durable_reconcile / resume_durable_workflow for multi-step DAG.\n"
        "Typed A2A: run_typed_a2a_aging for structured invoice specialist handoffs.\n"
        "Circuit: circuit_status if tools fail with circuit_open.\n"
        "Always cite evidence_id. For write-offs say needs_review.\n"
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
        resolve_portal_with_fallback,
        request_approval,
        list_pending_approvals,
        decide_approval,
        start_durable_reconcile,
        resume_durable_workflow,
        get_workflow_status,
        run_typed_a2a_aging,
        circuit_status,
        reset_circuit_breaker,
    ],
    sub_agents=[invoice_agent, payments_agent, contracts_agent, reconciliation_agent],
)
