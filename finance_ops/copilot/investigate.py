"""Bounded investigate playbook — matching.py candidates + cited structured draft.

Deterministic by default (CI-safe). Optional LLM summary when API keys are present
and COPILOT_FORCE_DETERMINISTIC is unset / false.
"""

from __future__ import annotations

import json
import os
from typing import Any

from finance_ops.ar_queue.domain.matching import score_against_invoices
from finance_ops.copilot.config import (
    _truthy,
    copilot_email_evidence_enabled,
    copilot_mode,
    remittance_pdf_extract_enabled,
)
from finance_ops.copilot import store as case_store
from finance_ops.copilot.email_evidence import retrieve_email_evidence
from finance_ops.copilot.remittance import (
    extract_remittance_document,
    is_thin_remittance_text,
)
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


PROMPT_VERSION = "copilot-investigate-v2"
MODEL_STUB = "deterministic-structured-v2"
MODEL_RULES = "rules_only"
RETRIEVER_VERSION = "copilot-evidence-v2"


def _force_deterministic() -> bool:
    return _truthy("COPILOT_FORCE_DETERMINISTIC")


def _llm_available() -> bool:
    if _force_deterministic():
        return False
    return bool(
        os.getenv("GOOGLE_API_KEY", "").strip()
        or os.getenv("GEMINI_API_KEY", "").strip()
    )


def load_payment_score_context(
    *,
    payment_id: str,
    customer_id: str | None = None,
    resolve_customer_from_payment: bool = False,
) -> dict[str, Any]:
    """Shared warehouse payment + invoice + matching load for evidence/investigate.

    When ``resolve_customer_from_payment`` is True (investigate path), missing
    ``customer_id`` falls back to the payment row. Evidence GET keeps the
    exception-row customer only so list behavior stays unchanged.
    """
    pid = payment_id.strip().upper() if payment_id else ""
    payment = repo.get_payment(pid) if pid else None
    resolved_customer = str(customer_id) if customer_id else None
    invoices: list[dict[str, Any]] = []

    if resolved_customer:
        invoices = list(repo.list_invoices(customer_id=resolved_customer) or [])
    elif resolve_customer_from_payment and payment:
        cust = payment.get("customer_id")
        if cust:
            resolved_customer = str(cust)
            invoices = list(repo.list_invoices(customer_id=resolved_customer) or [])

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

    return {
        "payment_id": pid,
        "customer_id": resolved_customer,
        "payment": payment,
        "invoices": invoices,
        "scored": scored,
    }


def _confidence_from_candidate(
    top: dict[str, Any] | None,
    *,
    thin_remittance: bool,
) -> ConfidenceBand:
    if not top:
        return "insufficient"
    score = float(top.get("score") or 0)
    reasons = {str(r) for r in (top.get("reasons") or [])}
    strong = bool(reasons & {"invoice_id_in_reference", "po_in_reference"})
    if thin_remittance and not strong:
        return "insufficient"
    if score >= 1.0 and strong:
        return "high"
    if score >= 0.7:
        return "medium"
    if score >= 0.5 and strong:
        return "medium"
    if score > 0 and not strong:
        # Amount-only / weak cue — low, and often abstain via insufficient_data.
        return "low" if score >= 0.5 else "insufficient"
    if score > 0:
        return "low"
    return "insufficient"


def _should_abstain(
    top: dict[str, Any] | None,
    *,
    thin_remittance: bool,
    band: ConfidenceBand,
) -> bool:
    if not top or band == "insufficient":
        return True
    reasons = {str(r) for r in (top.get("reasons") or [])}
    strong = bool(reasons & {"invoice_id_in_reference", "po_in_reference"})
    if thin_remittance and not strong:
        return True
    # Amount-only weak cue: abstain (insufficient) rather than rubber-stamp.
    if not strong and float(top.get("score") or 0) < 0.7:
        return True
    return False


def build_evidence_pack(
    *,
    case_id: str,
    payment_id: str,
    customer_id: str | None,
    payment: dict[str, Any] | None,
    invoices: list[dict[str, Any]],
    scored: dict[str, Any],
    actor: str | None = "system",
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
        rem_doc = None
        if remittance_pdf_extract_enabled():
            rem_doc = extract_remittance_document(
                payment_id=payment_id,
                customer_id=customer_id,
                reference_text=ref or None,
            )
        if rem_doc is not None:
            items.append(
                EvidenceItem(
                    source_id=rem_doc.document_id or f"REM-{payment_id}",
                    source_type="remittance",
                    label=(
                        f"Remittance extract ({rem_doc.method}, "
                        f"conf={rem_doc.confidence:.2f})"
                    ),
                    fields=rem_doc.to_evidence_fields(),
                )
            )
        elif ref:
            items.append(
                EvidenceItem(
                    source_id=f"REM-{payment_id}",
                    source_type="remittance",
                    label="Remittance / bank reference text",
                    fields={
                        "text": ref,
                        "extracted_fields": {"raw_reference": ref},
                        "confidence": 0.4,
                        "thin_evidence": is_thin_remittance_text(ref),
                        "method": "bank_reference",
                    },
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
        email_items = retrieve_email_evidence(
            customer_id=customer_id,
            payment_id=payment_id,
            actor=actor,
            limit=5,
        )
        items.extend(email_items)

    return EvidencePack(
        case_id=case_id,
        customer_id=customer_id,
        payment_id=payment_id,
        items=items,
        email_enabled=email_on,
        retriever_version=RETRIEVER_VERSION,
    )


def _citations_from_evidence(
    *,
    evidence: EvidencePack,
    payment_id: str,
    top: dict[str, Any] | None,
    claim_prefix: str,
) -> list[Citation]:
    """Build citation_map only from retrieved evidence source ids."""
    by_id = {item.source_id: item for item in evidence.items}
    citations: list[Citation] = []

    def add(source_id: str, claim: str, span: str | None = None) -> None:
        item = by_id.get(source_id)
        if not item:
            return
        citations.append(
            Citation(
                source_id=source_id,
                source_type=item.source_type,
                span=span,
                claim=claim,
            )
        )

    add(payment_id, f"{claim_prefix}: payment under investigation", "amount/reference")
    rem_id = f"REM-{payment_id}"
    if rem_id in by_id:
        text = str((by_id[rem_id].fields or {}).get("text") or "")
        add(rem_id, f"{claim_prefix}: remittance reference", text[:80] or None)

    if top:
        inv_id = str(top["invoice_id"])
        add(
            inv_id,
            f"{claim_prefix}: candidate invoice score={top.get('score')}",
            "invoice_id/amount",
        )
        rule_id = f"RULE-{inv_id}"
        reasons = top.get("reasons") or []
        add(
            rule_id,
            f"{claim_prefix}: matching.py reasons",
            ",".join(str(r) for r in reasons) or None,
        )

    return citations


def _remittance_thin_from_evidence(
    evidence: EvidencePack,
    payment: dict[str, Any] | None,
) -> bool:
    """Prefer structured remittance extract confidence; fall back to bank reference."""
    for item in evidence.items:
        if item.source_type != "remittance":
            continue
        fields = item.fields or {}
        if "thin_evidence" in fields:
            return bool(fields.get("thin_evidence"))
        conf = fields.get("confidence")
        if conf is not None and float(conf) < 0.45:
            return True
        extracted = fields.get("extracted_fields") or {}
        if extracted.get("invoice_ids"):
            return False
        text = str(fields.get("text") or extracted.get("raw_reference") or "")
        if text:
            return is_thin_remittance_text(text)
    ref = str((payment or {}).get("reference") or "")
    return is_thin_remittance_text(ref) if ref else True


def _draft_hypothesis(
    *,
    case_id: str,
    payment_id: str,
    customer_id: str | None,
    payment: dict[str, Any] | None,
    scored: dict[str, Any],
    evidence: EvidencePack,
    rules_only: bool,
) -> MatchHypothesis:
    candidates = scored.get("candidates") or []
    top = candidates[0] if candidates else None
    thin_remittance = _remittance_thin_from_evidence(evidence, payment)

    band = _confidence_from_candidate(top, thin_remittance=thin_remittance)
    abstain = _should_abstain(top, thin_remittance=thin_remittance, band=band)

    lines: list[MatchLine] = []
    if top and not abstain:
        inv_id = str(top["invoice_id"])
        # Prefer invoice amount when amount cue is weak / partial; else payment.
        reasons = {str(r) for r in (top.get("reasons") or [])}
        pay_amt = float((payment or {}).get("amount") or 0)
        inv_amt = float(top.get("invoice_amount") or pay_amt or 0)
        if "amount_within_tolerance" in reasons or "invoice_id_in_reference" in reasons:
            amount = pay_amt or inv_amt
        elif "possible_partial" in reasons:
            amount = pay_amt or inv_amt
        else:
            amount = pay_amt or inv_amt
        lines.append(
            MatchLine(
                invoice_id=inv_id,
                amount=amount,
                rationale="; ".join(str(r) for r in (top.get("reasons") or []))
                or "rule_score",
            )
        )

    claim_prefix = "abstain" if abstain else "match"
    citations = _citations_from_evidence(
        evidence=evidence,
        payment_id=payment_id,
        top=top if not abstain else None,
        claim_prefix=claim_prefix,
    )
    # Even on abstain, cite payment + remittance so the UI has clickable sources.
    if abstain and not citations:
        citations = _citations_from_evidence(
            evidence=evidence,
            payment_id=payment_id,
            top=None,
            claim_prefix="abstain",
        )

    if abstain:
        band = "insufficient"

    model_id = MODEL_RULES if rules_only else MODEL_STUB
    used_llm = False
    if not rules_only and _llm_available():
        model_id = os.getenv("FINANCE_OPS_MODEL", "gemini-3.1-flash-lite")
        used_llm = True

    raw_notes = (
        "Abstain: thin or conflicting evidence; request more info or escalate"
        if abstain
        else (
            f"Structured draft from matching.py → {top['invoice_id']} "
            f"(score={top.get('score')}, reasons={top.get('reasons')})"
            if top
            else "Abstain: no rule candidates"
        )
    )
    if used_llm:
        raw_notes = f"{raw_notes} | llm_enrichment=available"

    return MatchHypothesis(
        case_id=case_id,
        payment_id=payment_id,
        customer_id=customer_id,
        lines=lines,
        citation_map=citations,
        confidence_band=band,
        model_id=model_id,
        prompt_version=PROMPT_VERSION,
        insufficient_data=abstain or not lines,
        raw_notes=raw_notes,
        edited=False,
    )


def _try_llm_summary(
    *,
    case_id: str,
    hypothesis: MatchHypothesis,
    scored: dict[str, Any],
    evidence: EvidencePack,
) -> str | None:
    """Optional one-shot summary. Returns None on any failure (CI stays deterministic)."""
    if not _llm_available():
        return None
    try:
        # Lazy import — google-adk / genai may be absent in slim environments.
        from google import genai  # type: ignore

        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        model = os.getenv("FINANCE_OPS_MODEL", "gemini-3.1-flash-lite")
        payload = {
            "case_id": case_id,
            "hypothesis": hypothesis.model_dump(),
            "candidates": (scored.get("candidates") or [])[:3],
            "evidence_ids": [i.source_id for i in evidence.items],
        }
        prompt = (
            "You are a cash-application copilot. In 2-3 sentences, summarize the "
            "match investigation for an AR analyst. Cite source_ids from evidence_ids "
            "only. If insufficient_data is true, say so clearly and do not invent invoices.\n"
            f"DATA:\n{json.dumps(payload, default=str)[:4000]}"
        )
        resp = client.models.generate_content(model=model, contents=prompt)
        text = getattr(resp, "text", None) or ""
        text = str(text).strip()
        return text[:1200] if text else None
    except Exception:
        return None


def _draft_summary(
    *,
    case_id: str,
    hypothesis: MatchHypothesis,
    scored: dict[str, Any],
    evidence: EvidencePack,
    rules_only: bool,
) -> InvestigationSummary:
    cands = scored.get("candidates") or []
    if hypothesis.insufficient_data:
        text = (
            "Insufficient data to propose a confident cash-app match. "
            "Request more remittance detail or escalate. "
            f"Cited sources: {[c.source_id for c in hypothesis.citation_map]}."
        )
    elif rules_only:
        top = cands[0]
        text = (
            f"Rules-only draft: recommend {top['invoice_id']} "
            f"(score={top.get('score')}, reasons={top.get('reasons')}). "
            "No generative summary (COPILOT_MODE=rules_only)."
        )
    else:
        llm_text = _try_llm_summary(
            case_id=case_id,
            hypothesis=hypothesis,
            scored=scored,
            evidence=evidence,
        )
        if llm_text:
            text = llm_text
        else:
            top = cands[0]
            text = (
                f"Structured investigation: payment aligns with {top['invoice_id']} "
                f"on conventional signals {top.get('reasons')}. "
                "Review clickable citations before Accept / Edit & ready-to-apply."
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
    """Run bounded retrieve → rule score → cited hypothesis (+ optional LLM summary)."""
    mode = copilot_mode()
    rules_only = mode == "rules_only"

    ctx = load_payment_score_context(
        payment_id=payment_id,
        customer_id=customer_id,
        resolve_customer_from_payment=True,
    )
    payment = ctx["payment"]
    invoices = ctx["invoices"]
    scored = ctx["scored"]
    customer_id = ctx["customer_id"]
    payment_id = ctx["payment_id"] or payment_id

    evidence = build_evidence_pack(
        case_id=case_id,
        payment_id=payment_id,
        customer_id=customer_id,
        payment=payment,
        invoices=invoices,
        scored=scored,
        actor=actor,
    )
    hypothesis = _draft_hypothesis(
        case_id=case_id,
        payment_id=payment_id,
        customer_id=customer_id,
        payment=payment,
        scored=scored,
        evidence=evidence,
        rules_only=rules_only,
    )
    summary = _draft_summary(
        case_id=case_id,
        hypothesis=hypothesis,
        scored=scored,
        evidence=evidence,
        rules_only=rules_only,
    )

    remittance_ids = [
        i.source_id for i in evidence.items if i.source_type == "remittance"
    ]
    email_ids = [i.source_id for i in evidence.items if i.source_type == "email"]
    invoice_ids = [
        i.source_id for i in evidence.items if i.source_type == "invoice"
    ]

    # Single overlay write (hypothesis + summary + audit) instead of 3 RMW cycles.
    case_store.persist_investigation(
        case_id,
        hypothesis=hypothesis,
        summary=summary,
        actor=actor,
        audit_detail={
            "case_id": case_id,
            "customer_id": customer_id,
            "payment_id": payment_id,
            "invoice_ids": invoice_ids,
            "remittance_ids": remittance_ids,
            "email_ids": email_ids,
            "retriever_version": evidence.retriever_version,
            "model_id": hypothesis.model_id,
            "prompt_version": hypothesis.prompt_version,
            "confidence_band": hypothesis.confidence_band,
            "citation_map": [c.model_dump() for c in hypothesis.citation_map],
            "raw_hypothesis": hypothesis.model_dump(),
            "mode": mode,
            "rules_only": rules_only,
            "candidate_count": len(scored.get("candidates") or []),
            "recommendation": scored.get("recommendation"),
            "email_evidence": evidence.email_enabled,
            "insufficient_data": hypothesis.insufficient_data,
        },
    )

    llm_skipped = (
        rules_only
        or _force_deterministic()
        or not _llm_available()
        or hypothesis.model_id in {MODEL_STUB, MODEL_RULES}
    )

    candidates = list(scored.get("candidates") or [])[:5]
    evidence_dump = evidence.model_dump()
    # Seed process cache so the next GET /evidence after investigate is free.
    from finance_ops.copilot.evidence_cache import cache_evidence_pack

    cache_evidence_pack(case_id, actor=actor, pack=evidence_dump)

    return {
        "status": "success",
        "case_id": case_id,
        "mode": mode,
        "rules_only": rules_only,
        "scored": {
            "recommendation": scored.get("recommendation"),
            "candidates": candidates,
        },
        "evidence": evidence_dump,
        "hypothesis": hypothesis.model_dump(),
        "summary": summary.model_dump(),
        "needs_review": True,
        "llm_skipped": llm_skipped,
    }
