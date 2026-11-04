"""Copilot domain types — structured hypothesis SoT (not free-form chat)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Decision(str, Enum):
    accept = "accept"
    edit_ready_to_apply = "edit_ready_to_apply"
    reject = "reject"
    escalate = "escalate"
    need_info = "need_info"


ConfidenceBand = Literal["high", "medium", "low", "insufficient"]


class Citation(BaseModel):
    source_id: str
    source_type: str  # payment | invoice | remittance | email | rule_match
    span: str | None = None
    claim: str | None = None


class MatchLine(BaseModel):
    invoice_id: str
    amount: float
    rationale: str | None = None


class MatchHypothesis(BaseModel):
    case_id: str
    payment_id: str
    customer_id: str | None = None
    lines: list[MatchLine] = Field(default_factory=list)
    citation_map: list[Citation] = Field(default_factory=list)
    confidence_band: ConfidenceBand = "insufficient"
    model_id: str | None = None
    prompt_version: str | None = None
    insufficient_data: bool = False
    raw_notes: str | None = None
    edited: bool = False


class InvestigationSummary(BaseModel):
    case_id: str
    summary: str
    confidence_band: ConfidenceBand = "insufficient"
    citation_map: list[Citation] = Field(default_factory=list)
    model_id: str | None = None
    prompt_version: str = "copilot-investigate-v1"
    rules_only: bool = False


class EvidenceItem(BaseModel):
    source_id: str
    source_type: str
    label: str
    fields: dict[str, Any] = Field(default_factory=dict)
    stub: bool = False


class EvidencePack(BaseModel):
    case_id: str
    customer_id: str | None = None
    payment_id: str | None = None
    items: list[EvidenceItem] = Field(default_factory=list)
    email_enabled: bool = False
    retriever_version: str = "copilot-evidence-v1"


class ApplyGuidancePacket(BaseModel):
    """Guidance-only apply packet for copy / deep-link into current ERP.

    Never posts cash. Warehouse apply is separate and demo-flag gated.
    """

    case_id: str
    customer_id: str | None = None
    payment_id: str
    invoice_ids: list[str] = Field(default_factory=list)
    lines: list[MatchLine] = Field(default_factory=list)
    total_amount: float | None = None
    currency: str = "USD"
    citations: list[Citation] = Field(default_factory=list)
    actor: str
    decision: Decision
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    erp_deep_link_hint: str | None = None
    copy_text: str | None = None
    warehouse_applied: bool = False
    warehouse_apply_result: dict[str, Any] | None = None


class Case(BaseModel):
    case_id: str
    exception_id: str | None = None
    lane: str = "cash_app"
    customer_id: str | None = None
    payment_id: str | None = None
    amount: float | None = None
    currency: str = "USD"
    status: str = "open"
    recommended_invoice_id: str | None = None
    match_score: float | None = None
    aging_days: int | None = None
    confidence_band: ConfidenceBand | None = None
    hypothesis: MatchHypothesis | None = None
    summary: InvestigationSummary | None = None
    last_decision: Decision | None = None
    reason_code: str | None = None
    guidance: ApplyGuidancePacket | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AuditEvent(BaseModel):
    ts: str
    event: str
    actor: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class HypothesisUpdate(BaseModel):
    lines: list[MatchLine]
    raw_notes: str | None = None
    confidence_band: ConfidenceBand | None = None


class DecisionRequest(BaseModel):
    decision: Decision
    actor: str = "pilot"
    reason_code: str | None = None
    notes: str | None = None
    hypothesis: HypothesisUpdate | None = None
