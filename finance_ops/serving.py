"""L6 Cloud Run HTTP surface — health + free AR visibility + gated writes.

Free (no auth): health, status, aging, suggest, AR list/metrics/skus/queue.
Paid / ops writes: require FINANCE_OPS_API_TOKEN (Bearer or X-API-Token).

Run locally:
  uvicorn finance_ops.serving:app --host 0.0.0.0 --port 8080

Cloud Run sets PORT; see deploy/entrypoint.sh.
"""

from __future__ import annotations

import hmac
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

app = FastAPI(title="finance_ops", version="0.7.0")


def _bearer_or_header_token(
    authorization: str | None,
    header_token: str | None,
) -> str:
    provided = (header_token or "").strip()
    if provided:
        return provided
    if authorization:
        auth = authorization.strip()
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
    return ""


def _write_token_expected() -> str:
    """API write token; falls back to governance token if only that is set."""
    return (
        os.getenv("FINANCE_OPS_API_TOKEN", "").strip()
        or os.getenv("FINANCE_OPS_GOVERNANCE_TOKEN", "").strip()
    )


def _writes_locked() -> bool:
    """Lock mutating routes on Cloud Run, or when explicitly enabled / token set."""
    if os.getenv("FINANCE_OPS_LOCK_WRITES", "").lower() in {"1", "true", "yes"}:
        return True
    if _write_token_expected():
        return True
    # Cloud Run always sets K_SERVICE — fail closed for free-wedge demos.
    if os.getenv("K_SERVICE", "").strip():
        return True
    return False


def write_auth_status() -> dict[str, Any]:
    locked = _writes_locked()
    return {
        "writes_locked": locked,
        "token_configured": bool(_write_token_expected()),
        "free_tier": "visibility",
        "hint": (
            "GET /v1/ar/* + suggest/aging are free; "
            "mutating routes need Authorization: Bearer <FINANCE_OPS_API_TOKEN>"
            if locked
            else "local/dev: writes open (set FINANCE_OPS_API_TOKEN or LOCK_WRITES=1)"
        ),
    }


def _require_governance_token(
    authorization: str | None = None,
    x_governance_token: str | None = None,
) -> None:
    """Fail closed: sweep/revoke HTTP routes need FINANCE_OPS_GOVERNANCE_TOKEN."""
    expected = os.getenv("FINANCE_OPS_GOVERNANCE_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="governance token not configured (FINANCE_OPS_GOVERNANCE_TOKEN)",
        )
    provided = _bearer_or_header_token(authorization, x_governance_token)
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="unauthorized governance call")


def _require_write_token(
    authorization: str | None = None,
    x_api_token: str | None = None,
) -> None:
    """Gate paid/ops mutating routes (HITL apply, sync, triage, bootstrap).

    - Token set or Cloud Run (K_SERVICE) or FINANCE_OPS_LOCK_WRITES → require auth
    - Local/dev with no token and no lock → allow (pytest / uvicorn smoke)
    """
    if not _writes_locked():
        return
    expected = _write_token_expected()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=(
                "write auth not configured — set FINANCE_OPS_API_TOKEN "
                "(or FINANCE_OPS_GOVERNANCE_TOKEN) on Cloud Run"
            ),
        )
    provided = _bearer_or_header_token(authorization, x_api_token)
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=401,
            detail=(
                "unauthorized write — free tier is read/suggest only; "
                "send Authorization: Bearer <token> or X-API-Token"
            ),
        )


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
        "auth": write_auth_status(),
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
        "auth": write_auth_status(),
    }


@app.post("/v1/search_policies")
def api_search_policies(body: SearchBody) -> dict[str, Any]:
    from finance_ops.tools.rag_tools import search_policies

    return search_policies(body.query, top_k=body.top_k)


@app.post("/v1/aging")
def api_aging(body: AgingBody) -> dict[str, Any]:
    from finance_ops.tools.invoice_tools import aging_summary

    return aging_summary(body.customer_id)


@app.get("/v1/ar_exception_queue")
def api_ar_exception_queue(markdown: bool = False) -> dict[str, Any]:
    """Slice 1 — Spike A + B exception queue story + metrics (no dashboard)."""
    from finance_ops.tools.queue_tools import ar_exception_queue_summary

    return ar_exception_queue_summary(include_markdown=markdown)


class ArTriageBody(BaseModel):
    stage_sample: bool = True
    request_hitl: bool = False
    notify_slack: bool = False
    use_live_hubspot: bool = True


@app.post("/v1/ar_exception_triage")
@app.post("/v1/ar/triage")
def api_ar_exception_triage(
    body: ArTriageBody | None = None,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> dict[str, Any]:
    """Slice 2 — ERP/HubSpot feed into durable triage (no auto-apply). Write-gated."""
    _require_write_token(authorization, x_api_token)
    from finance_ops.tools.queue_tools import start_ar_exception_triage

    body = body or ArTriageBody()
    return start_ar_exception_triage(
        stage_sample=body.stage_sample,
        request_hitl=body.request_hitl,
        notify_slack=body.notify_slack,
        use_live_hubspot=body.use_live_hubspot,
    )


@app.get("/v1/ar/exceptions")
def api_ar_list_exceptions(
    status: str = "open",
    lane: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """MVP product queue — list materialised ar_exceptions."""
    from finance_ops.services.queue_service import list_exceptions

    return list_exceptions(status=status or None, lane=lane, limit=limit)


@app.get("/v1/ar/exceptions/{exception_id}")
def api_ar_get_exception(exception_id: str) -> dict[str, Any]:
    from finance_ops.services.queue_service import get_exception

    out = get_exception(exception_id)
    if out.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=out)
    return out


@app.post("/v1/ar/exceptions/sync")
def api_ar_sync_exceptions(
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> dict[str, Any]:
    """Materialise open exceptions from warehouse payments / portal / gaps. Write-gated."""
    _require_write_token(authorization, x_api_token)
    from finance_ops.services.queue_service import sync_from_warehouse

    return sync_from_warehouse()


@app.get("/v1/ar/metrics")
def api_ar_metrics() -> dict[str, Any]:
    """Cached product metrics (projection + legacy Spike A/B aggregates)."""
    from finance_ops.services.queue_service import queue_metrics

    return queue_metrics(use_cache=True)


@app.get("/v1/ar/skus")
def api_ar_skus() -> dict[str, Any]:
    from finance_ops.services.sku_catalog import list_skus

    return list_skus()


@app.post("/v1/request_approval")
def api_request_approval(
    body: ApprovalBody,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> dict[str, Any]:
    _require_write_token(authorization, x_api_token)
    from finance_ops.tools.runtime_tools import request_approval

    return request_approval(
        kind=body.kind,
        amount=body.amount,
        summary=body.summary,
        related_ids=body.related_ids,
    )


@app.post("/v1/suggest_payment_match")
def api_suggest_payment_match(body: PaymentMatchBody) -> dict[str, Any]:
    """Free wedge — suggest only (no apply / no HITL)."""
    from finance_ops.tools.payment_tools import suggest_payment_match

    return suggest_payment_match(body.payment_id)


@app.post("/v1/request_cash_app_approval")
def api_request_cash_app_approval(
    body: PaymentMatchBody,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> dict[str, Any]:
    """Paid path — opens HITL / may apply. Requires write token on Cloud Run."""
    _require_write_token(authorization, x_api_token)
    from finance_ops.tools.payment_tools import request_cash_app_approval

    return request_cash_app_approval(body.payment_id, invoice_id=body.invoice_id or "")


@app.post("/v1/decide_approval")
def api_decide_approval(
    body: DecideBody,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> dict[str, Any]:
    _require_write_token(authorization, x_api_token)
    from finance_ops.tools.runtime_tools import decide_approval

    return decide_approval(
        body.approval_id,
        body.decision,
        resume_token=body.resume_token,
        actor=body.actor,
    )


@app.post("/v1/bootstrap")
def api_bootstrap(
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> dict[str, Any]:
    """Idempotent warehouse + vector + graph sync for cold Cloud Run instances."""
    _require_write_token(authorization, x_api_token)
    from data_plane.graph.sync import sync_knowledge_graph
    from data_plane.vectors.embed import build_policy_index
    from pipelines.batch.ingest import ingest_batch

    batch = ingest_batch(run_id="cloudrun-bootstrap")
    vectors = build_policy_index()
    graph = sync_knowledge_graph()
    return {"status": "success", "batch": batch, "vectors": vectors, "graph": graph}


@app.post("/v1/governance/sweep")
def api_governance_sweep(
    authorization: str | None = Header(default=None),
    x_governance_token: str | None = Header(default=None, alias="X-Governance-Token"),
) -> dict[str, Any]:
    """Cloud Scheduler target: TTL + eval lifecycle sweep (retire / deprecate / revoke).

    Auth required — not an agent tool. Send `Authorization: Bearer <token>` or
    `X-Governance-Token` matching FINANCE_OPS_GOVERNANCE_TOKEN.
    """
    _require_governance_token(authorization, x_governance_token)
    from finance_ops.governance.registry import sweep_lifecycle

    return sweep_lifecycle()


@app.get("/v1/governance/agents")
def api_governance_agents(
    authorization: str | None = Header(default=None),
    x_governance_token: str | None = Header(default=None, alias="X-Governance-Token"),
) -> dict[str, Any]:
    _require_governance_token(authorization, x_governance_token)
    from finance_ops.governance.registry import list_agents

    return {"status": "success", "agents": list_agents(), "needs_review": False}


@app.post("/v1/hubspot/webhook")
async def api_hubspot_webhook(
    request: Request,
    x_hubspot_signature_v3: str | None = Header(default=None, alias="X-HubSpot-Signature-v3"),
    x_hubspot_request_timestamp: str | None = Header(
        default=None, alias="X-HubSpot-Request-Timestamp"
    ),
) -> dict[str, Any]:
    """D7 — HubSpot webhook: v3 signature + 5-min replay window; durable DAG by deal id."""
    from finance_ops.governance.audit import append_audit
    from finance_ops.integrations.hubspot_webhook import (
        extract_deal_id,
        parse_webhook_body,
        start_deal_workflow,
        validate_signature_v3,
    )

    raw = await request.body()
    # Full target URL as configured in HubSpot (override via env for local/ngrok).
    public_base = os.getenv("HITL_PUBLIC_BASE_URL", "").rstrip("/")
    if public_base:
        full_uri = f"{public_base}/v1/hubspot/webhook"
    else:
        full_uri = str(request.url)

    ok, reason = validate_signature_v3(
        method="POST",
        full_uri=full_uri,
        body=raw,
        timestamp_ms=x_hubspot_request_timestamp or "",
        signature=x_hubspot_signature_v3 or "",
    )
    if not ok:
        append_audit(
            event="hubspot_webhook",
            agent="serving",
            decision="deny",
            tool="hubspot_webhook",
            reason=reason,
        )
        raise HTTPException(status_code=401, detail=f"invalid_hubspot_signature:{reason}")

    try:
        payload = parse_webhook_body(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"invalid_json:{exc}") from exc

    deal_id = extract_deal_id(payload)
    if not deal_id:
        append_audit(
            event="hubspot_webhook",
            agent="serving",
            decision="ignore",
            tool="hubspot_webhook",
            reason="no_deal_id",
        )
        return {"status": "ignored", "reason": "no_deal_id", "needs_review": False}

    event = payload[0] if isinstance(payload, list) and payload else payload
    if not isinstance(event, dict):
        event = {"objectId": deal_id}
    result = start_deal_workflow(deal_id, event=event)
    append_audit(
        event="hubspot_webhook",
        agent="serving",
        decision="allow",
        tool="hubspot_webhook",
        args={"deal_id": deal_id},
        reason=result.get("workflow_status"),
        extra={"run_id": result.get("run_id")},
    )
    return result
