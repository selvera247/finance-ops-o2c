"""Bounded investigate playbook — rules first, optional LLM summary stub."""

from __future__ import annotations

import os
from typing import Any

from finance_ops.ar_queue.domain.matching import score_against_invoices
from finance_ops.copilot.config import (
    copilot_email_evidence_enabled,
    copilot_mode,
)
from finance_ops.copilot import store as case_store
from finance_ops.copilot.types import (
    Citation,
    ConfidenceBand,
    EvidenceItem,
    EvidencePack,
    InvestigationSummary,
    MatchHypothesis,
    MatchLine,
)
from data_plane import repository as repo


PROMPT_VERSION = "copilot-investigate-v1"
MODEL_STUB = "deterministic-stub"
MODEL_RULES = "rules_only"


def _confidence_from_score(score: float | None, has_candidates: bool) -> ConfidenceBand:
    if not has_candidates or score is None:
        return "insufficient"
    if score >= 1.0:
        return "high"
    if score >= 0.7:
        return "medium"
    if score > 0:
        return "low"
    return "insufficient"


def build_evidence_pack(
    *,
    case_id: str,
    payment_id: str,
    customer_id: str | None,
    payment: dict[str, Any] | None,
    invoices: list[dict[str, Any]],
    scored: dict[str, Any],
) -> EvidencePack:
    items: list[EvidenceItem] = []
    if payment:
        items.append(
            EvidenceItem(
                source_id=str(payment.get("payment_id") or payment_id),
                source_type="payment",
                label="Unmatched payment",
                fields={
                    k: payment.get(k)
                    for k in (
                        "payment_id",
                        "customer_id",
                        "amount",
                        "currency",
                        "reference",
                        "status",
                        "received_at",
                    )
                },
            )
        )
        ref = str(payment.get("reference") or "")
        if ref:
            items.append(
                EvidenceItem(
                    source_id=f"REM-{payment_id}",
                    source_type="remittance",
                    label="Remittance / bank reference text",
                    fields={"text": ref, "extracted_fields": {"raw_reference": ref}},
                )
            )

    for inv in invoices[:20]:
        items.append(
            EvidenceItem(
                source_id=str(inv.get("invoice_id")),
                source_type="invoice",
                label=f"Open invoice {inv.get('invoice_id')}",
                fields={
                    k: inv.get(k)
                    for k in (
                        "invoice_id",
                        "customer_id",
                        "amount",
                        "status",
                        "po_number",
                        "currency",
                    )
                },
            )
        )

    for cand in (scored.get("candidates") or [])[:5]:
        items.append(
            EvidenceItem(
                source_id=f"RULE-{cand.get('invoice_id')}",
                source_type="rule_match",
                label=f"Rule candidate {cand.get('invoice_id')} score={cand.get('score')}",
                fields=cand,
            )
        )

    email_on = copilot_email_evidence_enabled()
    if email_on and customer_id:
        items.append(
            EvidenceItem(
                source_id=f"EMAIL-STUB-{customer_id}",
                source_type="email",
                label="Email remittance thread (stub — ACL pending Week 5–6)",
                fields={
                    "subject": f"Payment advice for {payment_id}",
                    "snippet": "Stub: email retrieve gated on A3 / COPILOT_EMAIL_EVIDENCE",
                    "customer_id": customer_id,
                },
                stub=True,
            )
        )

    return EvidencePack(
        case_id=case_id,
        customer_id=customer_id,
        payment_id=payment_id,
        items=items,
        email_enabled=email_on,
    )


def _draft_hypothesis(
    *,
    case_id: str,
    payment_id: str,
    customer_id: str | None,
    payment: dict[str, Any] | None,
    scored: dict[str, Any],
    rules_only: bool,
) -> MatchHypothesis:
    candidates = scored.get("candidates") or []
    top = candidates[0] if candidates else None
    lines: list[MatchLine] = []
    citations: list[Citation] = []

    if payment:
        citations.append(
            Citation(
                source_id=payment_id,
                source_type="payment",
                span="amount/reference",
                claim="payment under investigation",
            )
        )
        ref = str(payment.get("reference") or "")
        if ref:
            citations.append(
                Citation(
                    source_id=f"REM-{payment_id}",
                    source_type="remittance",
                    span=ref[:80],
                    claim="remittance reference text",
                )
            )

    if top:
        inv_id = str(top["invoice_id"])
        amount = float(
            (payment or {}).get("amount")
            or top.get("invoice_amount")
            or 0
        )
        reasons = top.get("reasons") or []
        lines.append(
            MatchLine(
                invoice_id=inv_id,
                amount=amount,
                rationale="; ".join(str(r) for r in reasons) or "rule_score",
            )
        )
        citations.append(
            Citation(
                source_id=inv_id,
                source_type="invoice",
                span="invoice_id/amount",
                claim=f"candidate match score={top.get('score')}",
            )
        )
        citations.append(
            Citation(
                source_id=f"RULE-{inv_id}",
                source_type="rule_match",
                span=",".join(str(r) for r in reasons),
                claim="conventional matching.py reasons",
            )
        )

    band = _confidence_from_score(
        float(top["score"]) if top else None,
        bool(candidates),
    )
    insufficient = band == "insufficient" or not lines

    model_id = MODEL_RULES if rules_only else MODEL_STUB
    # Optional: if API key present and not rules_only, still use stub in CI —
    # real LLM draft lands Weeks 5–6. Record intent when key exists.
    if not rules_only and os.getenv("GOOGLE_API_KEY", "").strip():
        model_id = os.getenv("FINANCE_OPS_MODEL", "gemini-3.1-flash-lite") + "+stub"

    return MatchHypothesis(
        case_id=case_id,
        payment_id=payment_id,
        customer_id=customer_id,
        lines=lines,
        citation_map=citations,
        confidence_band=band,
        model_id=model_id,
        prompt_version=PROMPT_VERSION,
        insufficient_data=insufficient,
        raw_notes=(
            "Abstain: no rule candidates"
            if insufficient
            else f"Top candidate {top['invoice_id']} via matching.py"
            if top
            else None
        ),
        edited=False,
    )


def _draft_summary(
    *,
    case_id: str,
    hypothesis: MatchHypothesis,
    scored: dict[str, Any],
    rules_only: bool,
) -> InvestigationSummary:
    cands = scored.get("candidates") or []
    if hypothesis.insufficient_data:
        text = (
            "Insufficient data to propose a confident cash-app match. "
            "Request more remittance detail or escalate."
        )
    elif rules_only:
        top = cands[0]
        text = (
            f"Rules-only draft: recommend {top['invoice_id']} "
            f"(score={top.get('score')}, reasons={top.get('reasons')}). "
            "No generative summary (COPILOT_MODE=rules_only)."
        )
    else:
        top = cands[0]
        text = (
            f"Investigation stub: payment aligns with {top['invoice_id']} "
            f"on conventional signals {top.get('reasons')}. "
            "Review citations before Accept / Edit & ready-to-apply."
        )

    return InvestigationSummary(
        case_id=case_id,
        summary=text,
        confidence_band=hypothesis.confidence_band,
        citation_map=list(hypothesis.citation_map),
        model_id=hypothesis.model_id,
        prompt_version=PROMPT_VERSION,
        rules_only=rules_only,
    )


def investigate_case(
    *,
    case_id: str,
    payment_id: str,
    customer_id: str | None,
    actor: str = "system",
) -> dict[str, Any]:
    """Run bounded retrieve → rule score → draft hypothesis (+ optional stub summary)."""
    mode = copilot_mode()
    rules_only = mode == "rules_only"

    payment = repo.get_payment(payment_id.strip().upper())
    invoices: list[dict[str, Any]] = []
    if customer_id:
        invoices = list(repo.list_invoices(customer_id=customer_id) or [])
    elif payment:
        cust = payment.get("customer_id")
        if cust:
            invoices = list(repo.list_invoices(customer_id=str(cust)) or [])
            customer_id = str(cust)

    if payment:
        scored = score_against_invoices(payment, invoices)
    else:
        scored = {
            "status": "not_found",
            "payment": None,
            "candidates": [],
            "recommendation": None,
            "needs_review": True,
        }

    evidence = build_evidence_pack(
        case_id=case_id,
        payment_id=payment_id,
        customer_id=customer_id,
        payment=payment,
        invoices=invoices,
        scored=scored,
    )
    hypothesis = _draft_hypothesis(
        case_id=case_id,
        payment_id=payment_id,
        customer_id=customer_id,
        payment=payment,
        scored=scored,
        rules_only=rules_only,
    )
    summary = _draft_summary(
        case_id=case_id,
        hypothesis=hypothesis,
        scored=scored,
        rules_only=rules_only,
    )

    case_store.set_hypothesis(case_id, hypothesis)
    case_store.set_summary(case_id, summary)
    case_store.append_audit(
        case_id,
        "investigate",
        actor=actor,
        detail={
            "mode": mode,
            "rules_only": rules_only,
            "candidate_count": len(scored.get("candidates") or []),
            "recommendation": scored.get("recommendation"),
            "confidence_band": hypothesis.confidence_band,
            "model_id": hypothesis.model_id,
            "email_evidence": evidence.email_enabled,
        },
    )

    return {
        "status": "success",
        "case_id": case_id,
        "mode": mode,
        "rules_only": rules_only,
        "scored": {
            "recommendation": scored.get("recommendation"),
            "candidates": scored.get("candidates") or [],
        },
        "evidence": evidence.model_dump(),
        "hypothesis": hypothesis.model_dump(),
        "summary": summary.model_dump(),
        "needs_review": True,
        "llm_skipped": rules_only or hypothesis.model_id in {MODEL_STUB, MODEL_RULES}
        or "+stub" in str(hypothesis.model_id or ""),
    }
