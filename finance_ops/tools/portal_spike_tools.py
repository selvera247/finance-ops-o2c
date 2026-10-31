"""Spike B — portal extract exception review + walkthrough helpers.

Pure classification lives in ``finance_ops.ar_queue.domain.portal_classify``.
"""

from __future__ import annotations

from typing import Any

from data_plane import repository as repo
from finance_ops.ar_queue.domain.portal_classify import (
    SPIKE_B_WALKTHROUGH,
    classify_portal_row,
)
from finance_ops.ar_queue.domain.serialize import clean_row as _clean
from finance_ops.lib.evidence import record_evidence
from finance_ops.runtime.circuit_breaker import DEFAULT_BREAKER, CircuitOpenError


def _guard(name: str) -> None:
    DEFAULT_BREAKER.record_tool(name)


def _find_extract(claim_id: str) -> dict[str, Any] | None:
    claim_id = claim_id.strip().upper()
    for row in repo.portal_extracts(portal_id="payer_availity"):
        if str(row.get("external_id") or "").upper() == claim_id:
            return row
    # Fallback any portal
    for row in repo.portal_extracts():
        if str(row.get("external_id") or "").upper() == claim_id:
            return row
    return None


def classify_portal_exception(claim_id: str) -> dict[str, Any]:
    """Classify a Spike B / portal extract line for review routing."""
    try:
        _guard("classify_portal_exception")
    except CircuitOpenError as exc:
        return {"status": "circuit_open", "error": str(exc), "needs_review": True}

    claim_id = claim_id.strip().upper()
    row = _find_extract(claim_id)
    result = classify_portal_row(claim_id, row)
    if result.get("status") != "success":
        result["evidence"] = record_evidence(
            agent="coordinator",
            action="classify_portal_exception",
            inputs={"claim_id": claim_id},
            outputs=result,
            sources=[],
        )
        return result

    result["evidence"] = record_evidence(
        agent="coordinator",
        action="classify_portal_exception",
        inputs={"claim_id": claim_id},
        outputs={
            "disposition": result.get("disposition"),
            "hitl_kind": result.get("hitl_kind"),
            "suggested_invoice_ids": result.get("suggested_invoice_ids"),
        },
        sources=[repo.source_label() + ":portal_extracts"],
    )
    return result


def request_portal_extract_review(
    claim_id: str,
    notify_slack: bool = True,
) -> dict[str, Any]:
    """Open HITL for a portal extract exception (denied / orphan / accept remittance)."""
    try:
        _guard("request_portal_extract_review")
    except CircuitOpenError as exc:
        return {"status": "circuit_open", "error": str(exc), "needs_review": True}

    from finance_ops.runtime.hitl import DEFAULT_STORE
    from finance_ops.runtime.slack_hitl import approval_links, notify_slack as slack_notify

    classified = classify_portal_exception(claim_id)
    if classified.get("status") != "success":
        return classified

    kind = str(classified["hitl_kind"])
    amount = float(classified.get("amount") or 0)
    disposition = classified["disposition"]
    invoices = classified.get("suggested_invoice_ids") or []
    summary = f"Portal extract {claim_id}: {disposition}"
    if invoices:
        summary += f" → {', '.join(invoices)}"

    approval = DEFAULT_STORE.create(
        kind=kind,
        amount=amount,
        summary=summary,
        payload={
            "claim_id": claim_id,
            "disposition": disposition,
            "suggested_invoice_ids": invoices,
            "extract": classified.get("extract"),
            "related_ids": [claim_id, *invoices],
        },
    )
    links = approval_links(approval)
    slack = slack_notify(approval) if notify_slack else {"sent": False, "skipped": True}
    result = {
        "status": "pending",
        "claim_id": claim_id,
        "disposition": disposition,
        "classification": {
            "hitl_kind": kind,
            "suggested_invoice_ids": invoices,
        },
        "approval": approval.model_dump(),
        "links": links,
        "slack": slack,
        "needs_review": True,
        "resume_hint": (
            "Approve to accept disposition in ops narrative; reject to leave in exception queue. "
            f"{links.get('approve')}"
        ),
    }
    result["evidence"] = record_evidence(
        agent="coordinator",
        action="request_portal_extract_review",
        inputs={"claim_id": claim_id},
        outputs={
            "approval_id": approval.approval_id,
            "kind": kind,
            "slack_sent": slack.get("sent"),
        },
        sources=[repo.source_label() + ":portal_extracts", "hitl:approval_store"],
    )
    return result


def spike_b_walkthrough() -> dict[str, Any]:
    """Classify the three Spike B walkthrough claims (load_spike_b first)."""
    try:
        _guard("spike_b_walkthrough")
    except CircuitOpenError as exc:
        return {"status": "circuit_open", "error": str(exc), "needs_review": True}

    items = [classify_portal_exception(cid) for cid in SPIKE_B_WALKTHROUGH]
    result = {
        "status": "success",
        "portal_id": "payer_availity",
        "walkthrough": items,
        "needs_review": any(i.get("needs_review") for i in items),
    }
    result["evidence"] = record_evidence(
        agent="coordinator",
        action="spike_b_walkthrough",
        inputs={"claim_ids": list(SPIKE_B_WALKTHROUGH)},
        outputs={"count": len(items)},
        sources=["spike_b", repo.source_label() + ":portal_extracts"],
    )
    return result
