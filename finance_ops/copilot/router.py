"""HTTP routes for Cash-Application Exception Copilot."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from finance_ops.copilot import service as copilot_service
from finance_ops.copilot.config import (
    copilot_email_evidence_enabled,
    copilot_mode,
    demo_apply_enabled,
    digest_enabled,
    digest_send_enabled,
    prototype_mode_label,
)
from finance_ops.copilot.types import DecisionRequest, HypothesisUpdate, MatchLine

router = APIRouter(prefix="/v1/copilot", tags=["copilot"])


class InvestigateBody(BaseModel):
    actor: str = "api"


class HypothesisBody(BaseModel):
    lines: list[MatchLine]
    raw_notes: str | None = None
    confidence_band: str | None = None
    actor: str = "api"


def _gate_writes(
    authorization: str | None,
    x_api_token: str | None,
) -> None:
    from finance_ops.serving import _require_write_token

    _require_write_token(authorization, x_api_token)


@router.get("/status")
def copilot_status() -> dict[str, Any]:
    return {
        "status": "ok",
        "product": "cash_application_exception_copilot",
        "mode": copilot_mode(),
        "prototype_mode": prototype_mode_label(),
        "email_evidence": copilot_email_evidence_enabled(),
        "demo_apply": demo_apply_enabled(),
        "digest_enabled": digest_enabled(),
        "digest_send": digest_send_enabled(),
        "guidance_only": not demo_apply_enabled(),
        "auto_allow_on_copilot_path": False,
        "modes": {
            "A": "COPILOT_MODE=workbench COPILOT_EMAIL_EVIDENCE=0",
            "B": "COPILOT_MODE=workbench COPILOT_EMAIL_EVIDENCE=1",
            "C": "COPILOT_MODE=slack_contrast (Slack HITL contrast; not primary UX)",
            "D": "COPILOT_MODE=rules_only (skip LLM draft)",
        },
    }


@router.get("/digest")
def get_digest(
    force: bool = False,
    sync: bool = False,
    limit: int | None = None,
    min_confidence: str | None = None,
) -> dict[str, Any]:
    """Optional ranked exception digest (off by default). Use ?force=1 for dry-run."""
    from finance_ops.copilot.digest import run_digest

    return run_digest(
        sync_first=sync,
        force=force,
        limit=limit,
        min_confidence=min_confidence,
    )


@router.get("/queue")
def get_queue(
    status: str = "open",
    lane: str | None = "cash_app",
    limit: int = 50,
    sync: bool = False,
) -> dict[str, Any]:
    """Ranked Copilot exception queue (aging × amount × confidence)."""
    return copilot_service.list_queue(
        status=status or None,
        lane=lane,
        limit=limit,
        sync_first=sync,
    )


@router.get("/cases/{case_id}")
def get_case(case_id: str) -> dict[str, Any]:
    out = copilot_service.get_case(case_id)
    if out.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=out)
    return out


@router.get("/cases/{case_id}/evidence")
def get_evidence(
    case_id: str,
    actor: str = "api",
) -> dict[str, Any]:
    out = copilot_service.get_evidence(case_id, actor=actor)
    if out.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=out)
    return out


@router.post("/cases/{case_id}/investigate")
def post_investigate(
    case_id: str,
    body: InvestigateBody | None = None,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> dict[str, Any]:
    _gate_writes(authorization, x_api_token)
    body = body or InvestigateBody()
    out = copilot_service.investigate(case_id, actor=body.actor)
    if out.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=out)
    if out.get("status") == "error":
        raise HTTPException(status_code=400, detail=out)
    return out


@router.post("/cases/{case_id}/hypothesis")
def post_hypothesis(
    case_id: str,
    body: HypothesisBody,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> dict[str, Any]:
    _gate_writes(authorization, x_api_token)
    update = HypothesisUpdate(
        lines=body.lines,
        raw_notes=body.raw_notes,
        confidence_band=body.confidence_band,  # type: ignore[arg-type]
    )
    out = copilot_service.update_hypothesis(case_id, update, actor=body.actor)
    if out.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=out)
    return out


@router.post("/cases/{case_id}/decision")
def post_decision(
    case_id: str,
    body: DecisionRequest,
    authorization: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> dict[str, Any]:
    """Accept | Edit & ready-to-apply | Reject | Escalate | Need-info.

    Accept / edit emit ApplyGuidancePacket. Warehouse apply only if
    FINANCE_OPS_DEMO_APPLY=1. Never auto-applies from policy thresholds.
    """
    _gate_writes(authorization, x_api_token)
    out = copilot_service.decide(case_id, body)
    if out.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=out)
    if out.get("status") == "error":
        raise HTTPException(status_code=400, detail=out)
    return out


@router.get("/cases/{case_id}/audit")
def get_audit(case_id: str) -> dict[str, Any]:
    out = copilot_service.get_audit(case_id)
    if out.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=out)
    return out
