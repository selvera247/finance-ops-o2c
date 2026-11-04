"""Copilot application service — queue, evidence, hypothesis, decision, audit."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from finance_ops.ar_queue.application.queries import get_exception, list_exceptions
from finance_ops.ar_queue.application.sync import sync_from_warehouse, upsert_exception
from finance_ops.ar_queue.domain.ids import exception_id as make_exception_id
from finance_ops.ar_queue.domain.statuses import (
    COPILOT_QUEUE_STATUSES,
    OPEN_STATUSES,
    status_for_decision,
)
from finance_ops.copilot import store as case_store
from finance_ops.copilot.config import (
    copilot_email_evidence_enabled,
    copilot_mode,
    demo_apply_enabled,
    prototype_mode_label,
)
from finance_ops.copilot.investigate import build_evidence_pack, investigate_case
from finance_ops.copilot.reasons import validate_reason_code
from finance_ops.copilot.types import (
    ApplyGuidancePacket,
    Case,
    Citation,
    Decision,
    DecisionRequest,
    HypothesisUpdate,
    InvestigationSummary,
    MatchHypothesis,
)
from finance_ops.ar_queue.domain.matching import score_against_invoices
from data_plane import repository as repo


def _aging_days(opened_at: Any) -> int | None:
    if not opened_at:
        return None
    try:
        if isinstance(opened_at, str):
            ts = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
        else:
            ts = opened_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - ts).days)
    except (TypeError, ValueError):
        return None


def _rank_key(row: dict[str, Any]) -> tuple[float, float, float]:
    """aging × amount × inverse confidence — higher first."""
    aging = float(_aging_days(row.get("opened_at")) or 0)
    amount = float(row.get("amount") or 0)
    score = float(row.get("match_score") or 0)
    # Prefer older + larger + lower confidence (needs human)
    return (aging * amount * (1.5 - min(score, 1.2)), amount, aging)


def _row_to_case(row: dict[str, Any], overlay: dict[str, Any] | None = None) -> Case:
    overlay = overlay or case_store.load_overlay(str(row["exception_id"]))
    hyp = overlay.get("hypothesis")
    summary = overlay.get("summary")
    guidance = overlay.get("guidance")
    return Case(
        case_id=str(row["exception_id"]),
        exception_id=str(row["exception_id"]),
        lane=str(row.get("lane") or "cash_app"),
        customer_id=row.get("customer_id"),
        payment_id=row.get("source_id") if row.get("source_type") == "payment" else row.get("source_id"),
        amount=float(row["amount"]) if row.get("amount") is not None else None,
        currency=str(row.get("currency") or "USD"),
        status=str(row.get("status") or "open"),
        recommended_invoice_id=row.get("recommended_invoice_id"),
        match_score=float(row["match_score"]) if row.get("match_score") is not None else None,
        aging_days=_aging_days(row.get("opened_at")),
        confidence_band=(hyp or {}).get("confidence_band") if isinstance(hyp, dict) else None,
        hypothesis=MatchHypothesis.model_validate(hyp) if hyp else None,
        summary=InvestigationSummary.model_validate(summary) if summary else None,
        last_decision=overlay.get("last_decision"),
        reason_code=overlay.get("reason_code"),
        guidance=ApplyGuidancePacket.model_validate(guidance) if guidance else None,
        payload=row.get("payload") if isinstance(row.get("payload"), dict) else {},
    )


def ensure_queue(*, sync: bool = True) -> dict[str, Any]:
    """Materialize Spike A / warehouse exceptions into the Copilot queue."""
    if sync:
        return sync_from_warehouse()
    return {"status": "skipped", "synced_count": 0}


def list_queue(
    *,
    status: str | None = "open",
    lane: str | None = "cash_app",
    limit: int = 50,
    sync_first: bool = False,
) -> dict[str, Any]:
    if sync_first:
        ensure_queue(sync=True)

    # "open" for Copilot includes investigation + post-decision waiting statuses
    listed = list_exceptions(status=status, lane=lane, limit=max(limit, 200))
    rows = list(listed.get("exceptions") or [])
    if status == "open":
        rows = [r for r in rows if str(r.get("status")) in COPILOT_QUEUE_STATUSES]
    rows.sort(key=_rank_key, reverse=True)
    rows = rows[:limit]
    cases = [_row_to_case(r).model_dump() for r in rows]
    return {
        "status": "success",
        "count": len(cases),
        "cases": cases,
        "mode": copilot_mode(),
        "prototype_mode": prototype_mode_label(),
        "email_evidence": copilot_email_evidence_enabled(),
        "demo_apply": demo_apply_enabled(),
        "needs_review": any(c.get("status") in OPEN_STATUSES for c in cases),
    }


def get_case(case_id: str) -> dict[str, Any]:
    got = get_exception(case_id)
    if got.get("status") != "success":
        return {
            "status": "not_found",
            "case_id": case_id,
            "needs_review": True,
        }
    case = _row_to_case(got["exception"])
    return {
        "status": "success",
        "case": case.model_dump(),
        "mode": copilot_mode(),
        "prototype_mode": prototype_mode_label(),
        "needs_review": case.status in OPEN_STATUSES,
    }


def get_evidence(case_id: str) -> dict[str, Any]:
    got = get_exception(case_id)
    if got.get("status") != "success":
        return {"status": "not_found", "case_id": case_id}
    row = got["exception"]
    payment_id = str(row.get("source_id") or "")
    customer_id = row.get("customer_id")
    payment = repo.get_payment(payment_id) if payment_id else None
    invoices = list(repo.list_invoices(customer_id=str(customer_id)) or []) if customer_id else []
    scored = (
        score_against_invoices(payment, invoices)
        if payment
        else {"candidates": [], "recommendation": None}
    )
    pack = build_evidence_pack(
        case_id=case_id,
        payment_id=payment_id,
        customer_id=str(customer_id) if customer_id else None,
        payment=payment,
        invoices=invoices,
        scored=scored,
    )
    case_store.append_audit(
        case_id,
        "evidence_retrieved",
        actor="api",
        detail={"item_count": len(pack.items), "email_enabled": pack.email_enabled},
    )
    return {"status": "success", "evidence": pack.model_dump()}


def investigate(case_id: str, *, actor: str = "api") -> dict[str, Any]:
    got = get_exception(case_id)
    if got.get("status") != "success":
        return {"status": "not_found", "case_id": case_id}
    row = got["exception"]
    payment_id = str(row.get("source_id") or "")
    customer_id = str(row.get("customer_id") or "") or None
    if not payment_id:
        return {
            "status": "error",
            "error": "case_missing_payment_id",
            "case_id": case_id,
            "needs_review": True,
        }
    return investigate_case(
        case_id=case_id,
        payment_id=payment_id,
        customer_id=customer_id,
        actor=actor,
    )


def update_hypothesis(case_id: str, update: HypothesisUpdate, *, actor: str = "api") -> dict[str, Any]:
    got = get_exception(case_id)
    if got.get("status") != "success":
        return {"status": "not_found", "case_id": case_id}
    row = got["exception"]
    overlay = case_store.load_overlay(case_id)
    existing = overlay.get("hypothesis") or {}
    hyp = MatchHypothesis(
        case_id=case_id,
        payment_id=str(row.get("source_id") or existing.get("payment_id") or ""),
        customer_id=row.get("customer_id") or existing.get("customer_id"),
        lines=list(update.lines),
        citation_map=[
            Citation.model_validate(c) for c in (existing.get("citation_map") or [])
        ],
        confidence_band=update.confidence_band
        or existing.get("confidence_band")
        or "medium",
        model_id=existing.get("model_id"),
        prompt_version=existing.get("prompt_version"),
        insufficient_data=len(update.lines) == 0,
        raw_notes=update.raw_notes if update.raw_notes is not None else existing.get("raw_notes"),
        edited=True,
    )
    case_store.set_hypothesis(case_id, hyp)
    case_store.append_audit(
        case_id,
        "hypothesis_edited",
        actor=actor,
        detail={"lines": [ln.model_dump() for ln in hyp.lines]},
    )
    return {"status": "success", "hypothesis": hyp.model_dump()}


def _build_guidance(
    *,
    case_id: str,
    row: dict[str, Any],
    hypothesis: MatchHypothesis,
    decision: Decision,
    actor: str,
) -> ApplyGuidancePacket:
    invoice_ids = [ln.invoice_id for ln in hypothesis.lines]
    total = sum(float(ln.amount) for ln in hypothesis.lines) if hypothesis.lines else None
    payment_id = str(row.get("source_id") or hypothesis.payment_id)
    copy_lines = [
        f"Apply payment {payment_id} → {ln.invoice_id} amount={ln.amount}"
        for ln in hypothesis.lines
    ] or [f"No lines — review case {case_id}"]
    copy_text = (
        f"COPILOT APPLY GUIDANCE (do not auto-post)\n"
        f"case={case_id} customer={row.get('customer_id')} actor={actor}\n"
        + "\n".join(copy_lines)
    )
    return ApplyGuidancePacket(
        case_id=case_id,
        customer_id=row.get("customer_id"),
        payment_id=payment_id,
        invoice_ids=invoice_ids,
        lines=list(hypothesis.lines),
        total_amount=total,
        currency=str(row.get("currency") or "USD"),
        citations=list(hypothesis.citation_map),
        actor=actor,
        decision=decision,
        erp_deep_link_hint=f"erp://cash-app/apply?payment={payment_id}",
        copy_text=copy_text,
        warehouse_applied=False,
        warehouse_apply_result=None,
    )


def decide(case_id: str, body: DecisionRequest) -> dict[str, Any]:
    """Human decision → status + optional ApplyGuidancePacket. No silent apply."""
    # Hard guard: Copilot never auto-allows from policy thresholds.
    from finance_ops.governance.policy import load_policy

    policy = load_policy()
    auto_max = float((policy.get("thresholds") or {}).get("auto_allow_max") or 0)
    if auto_max > 0 and not demo_apply_enabled():
        # Soft warn only — still guidance-only; never silent apply on this path.
        pass

    got = get_exception(case_id)
    if got.get("status") != "success":
        return {"status": "not_found", "case_id": case_id}

    err = validate_reason_code(body.decision, body.reason_code)
    if err:
        return {"status": "error", "error": err, "case_id": case_id, "needs_review": True}

    row = dict(got["exception"])
    if body.hypothesis is not None:
        updated = update_hypothesis(case_id, body.hypothesis, actor=body.actor)
        if updated.get("status") != "success":
            return updated

    overlay = case_store.load_overlay(case_id)
    hyp_data = overlay.get("hypothesis")
    if not hyp_data and body.decision in {
        Decision.accept,
        Decision.edit_ready_to_apply,
    }:
        # Ensure investigate ran at least once
        inv = investigate(case_id, actor=body.actor)
        if inv.get("status") != "success":
            return inv
        overlay = case_store.load_overlay(case_id)
        hyp_data = overlay.get("hypothesis")

    if body.decision in {Decision.accept, Decision.edit_ready_to_apply}:
        if not hyp_data:
            return {
                "status": "error",
                "error": "hypothesis_required",
                "case_id": case_id,
                "needs_review": True,
            }
        hypothesis = MatchHypothesis.model_validate(hyp_data)
        if body.decision == Decision.accept and hypothesis.insufficient_data:
            return {
                "status": "error",
                "error": "insufficient_data_blocks_accept",
                "hint": "Use need_info, escalate, or edit lines first",
                "case_id": case_id,
                "needs_review": True,
            }
        if body.decision == Decision.edit_ready_to_apply:
            hypothesis = hypothesis.model_copy(update={"edited": True})
            case_store.set_hypothesis(case_id, hypothesis)

        guidance = _build_guidance(
            case_id=case_id,
            row=row,
            hypothesis=hypothesis,
            decision=body.decision,
            actor=body.actor,
        )

        warehouse_result = None
        if demo_apply_enabled() and hypothesis.lines:
            # Demo-only quarantine — call warehouse repo directly so policy
            # auto_allow_max=0 does not block the explicit demo flag. Copilot
            # happy path never reaches here when FINANCE_OPS_DEMO_APPLY is unset.
            from finance_ops.lib.evidence import record_evidence

            top = hypothesis.lines[0]
            applied = repo.apply_payment_match(guidance.payment_id, top.invoice_id)
            warehouse_result = {
                "status": "success" if applied.get("ok") else "error",
                "applied": applied,
                "demo_apply": True,
                "policy_note": "FINANCE_OPS_DEMO_APPLY=1 bypasses Copilot guidance-only",
            }
            warehouse_result["evidence"] = record_evidence(
                agent="copilot",
                action="demo_apply_payment_match",
                inputs={
                    "payment_id": guidance.payment_id,
                    "invoice_id": top.invoice_id,
                    "case_id": case_id,
                },
                outputs=warehouse_result,
                sources=[repo.source_label(), "flag:FINANCE_OPS_DEMO_APPLY"],
            )
            guidance = guidance.model_copy(
                update={
                    "warehouse_applied": bool(applied.get("ok")),
                    "warehouse_apply_result": warehouse_result,
                }
            )

        case_store.set_guidance(case_id, guidance)
        new_status = status_for_decision(body.decision)
        # If demo apply succeeded, mark resolved like legacy path
        if guidance.warehouse_applied:
            new_status = "resolved"
            row["resolved_at"] = datetime.now(timezone.utc)
            if hypothesis.lines:
                row["recommended_invoice_id"] = hypothesis.lines[0].invoice_id
        row["status"] = new_status
        upsert_exception(row)
        case_store.set_decision(
            case_id,
            decision=body.decision.value,
            reason_code=body.reason_code,
        )
        case_store.append_audit(
            case_id,
            "decision",
            actor=body.actor,
            detail={
                "decision": body.decision.value,
                "reason_code": body.reason_code,
                "notes": body.notes,
                "guidance": True,
                "warehouse_applied": guidance.warehouse_applied,
                "demo_apply": demo_apply_enabled(),
                "auto_allow_max": auto_max,
                "auto_apply_fired": False,
            },
        )
        return {
            "status": "success",
            "case_id": case_id,
            "decision": body.decision.value,
            "case_status": new_status,
            "guidance": guidance.model_dump(),
            "warehouse_applied": guidance.warehouse_applied,
            "auto_apply_fired": False,
            "needs_review": new_status in OPEN_STATUSES,
        }

    # reject / escalate / need_info — no guidance packet / no apply
    new_status = status_for_decision(body.decision)
    row["status"] = new_status
    upsert_exception(row)
    case_store.set_decision(
        case_id,
        decision=body.decision.value,
        reason_code=body.reason_code,
    )
    case_store.append_audit(
        case_id,
        "decision",
        actor=body.actor,
        detail={
            "decision": body.decision.value,
            "reason_code": body.reason_code,
            "notes": body.notes,
            "guidance": False,
            "warehouse_applied": False,
            "auto_apply_fired": False,
        },
    )
    return {
        "status": "success",
        "case_id": case_id,
        "decision": body.decision.value,
        "case_status": new_status,
        "reason_code": body.reason_code,
        "guidance": None,
        "warehouse_applied": False,
        "auto_apply_fired": False,
        "needs_review": new_status in OPEN_STATUSES,
    }


def get_audit(case_id: str) -> dict[str, Any]:
    got = get_exception(case_id)
    if got.get("status") != "success":
        # Still return overlay audit if any (case may be synthetic)
        overlay = case_store.load_overlay(case_id)
        if not overlay.get("audit"):
            return {"status": "not_found", "case_id": case_id}
    overlay = case_store.load_overlay(case_id)
    return {
        "status": "success",
        "case_id": case_id,
        "audit": overlay.get("audit") or [],
        "last_decision": overlay.get("last_decision"),
        "reason_code": overlay.get("reason_code"),
        "hypothesis": overlay.get("hypothesis"),
        "guidance": overlay.get("guidance"),
    }


def case_id_for_payment(payment_id: str) -> str:
    return make_exception_id("cash_app", payment_id.strip().upper())
