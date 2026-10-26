"""L6 Cloud Run HTTP surface — health + platform status + tool smokes.

Run locally:
  uvicorn finance_ops.serving:app --host 0.0.0.0 --port 8080

Cloud Run sets PORT; see deploy/entrypoint.sh.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="finance_ops", version="0.4.0")


class SearchBody(BaseModel):
    query: str = "collections escalation past due"
    top_k: int = 3


class AgingBody(BaseModel):
    customer_id: str = "CUST-ACME"


class ApprovalBody(BaseModel):
    kind: str = "write_off"
    amount: float = 125.0
    summary: str = "Cloud Run HITL smoke"
    related_ids: str = ""


class PaymentMatchBody(BaseModel):
    payment_id: str = "PAY-1001"
    invoice_id: str = ""


class DecideBody(BaseModel):
    approval_id: str
    decision: str = "approved"
    resume_token: str = ""
    actor: str = "api"


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "finance_ops",
        "model": os.getenv("FINANCE_OPS_MODEL", "gemini-3.1-flash-lite"),
        "data_mode": os.getenv("FINANCE_OPS_DATA_MODE", "warehouse"),
    }


@app.get("/v1/status")
def platform_status() -> dict[str, Any]:
    from finance_ops.tools.bigquery_tools import bigquery_status
    from finance_ops.tools.graph_tools import graph_status
    from data_plane.vectors.embed import vertex_vector_status

    return {
        "status": "success",
        "warehouse": bigquery_status(),
        "vectors": vertex_vector_status(),
        "graph": graph_status(),
    }


@app.post("/v1/search_policies")
def api_search_policies(body: SearchBody) -> dict[str, Any]:
    from finance_ops.tools.rag_tools import search_policies

    return search_policies(body.query, top_k=body.top_k)


@app.post("/v1/aging")
def api_aging(body: AgingBody) -> dict[str, Any]:
    from finance_ops.tools.invoice_tools import aging_summary

    return aging_summary(body.customer_id)


@app.post("/v1/request_approval")
def api_request_approval(body: ApprovalBody) -> dict[str, Any]:
    from finance_ops.tools.runtime_tools import request_approval

    return request_approval(
        kind=body.kind,
        amount=body.amount,
        summary=body.summary,
        related_ids=body.related_ids,
    )


@app.post("/v1/suggest_payment_match")
def api_suggest_payment_match(body: PaymentMatchBody) -> dict[str, Any]:
    from finance_ops.tools.payment_tools import suggest_payment_match

    return suggest_payment_match(body.payment_id)


@app.post("/v1/request_cash_app_approval")
def api_request_cash_app_approval(body: PaymentMatchBody) -> dict[str, Any]:
    from finance_ops.tools.payment_tools import request_cash_app_approval

    return request_cash_app_approval(body.payment_id, invoice_id=body.invoice_id or "")


@app.post("/v1/decide_approval")
def api_decide_approval(body: DecideBody) -> dict[str, Any]:
    from finance_ops.tools.runtime_tools import decide_approval

    return decide_approval(
        body.approval_id,
        body.decision,
        resume_token=body.resume_token,
        actor=body.actor,
    )


@app.post("/v1/bootstrap")
def api_bootstrap() -> dict[str, Any]:
    """Idempotent warehouse + vector + graph sync for cold Cloud Run instances."""
    from data_plane.graph.sync import sync_knowledge_graph
    from data_plane.vectors.embed import build_policy_index
    from pipelines.batch.ingest import ingest_batch

    batch = ingest_batch(run_id="cloudrun-bootstrap")
    vectors = build_policy_index()
    graph = sync_knowledge_graph()
    return {"status": "success", "batch": batch, "vectors": vectors, "graph": graph}


@app.post("/v1/governance/sweep")
def api_governance_sweep() -> dict[str, Any]:
    """Cloud Scheduler target: TTL + eval lifecycle sweep (retire / deprecate / revoke)."""
    from finance_ops.governance.registry import sweep_lifecycle

    return sweep_lifecycle()


@app.get("/v1/governance/agents")
def api_governance_agents() -> dict[str, Any]:
    from finance_ops.governance.registry import list_agents

    return {"status": "success", "agents": list_agents(), "needs_review": False}
