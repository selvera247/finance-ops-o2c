"""AR exception queue summary + slice 2 live feed triage tools."""

from __future__ import annotations

from typing import Any

from finance_ops.lib.evidence import record_evidence
from finance_ops.runtime.circuit_breaker import DEFAULT_BREAKER, CircuitOpenError
from finance_ops.runtime.exception_queue import build_ar_exception_queue


def _guard(name: str) -> None:
    DEFAULT_BREAKER.record_tool(name)


def ar_exception_queue_summary(include_markdown: bool = False) -> dict[str, Any]:
    """Spike A + Spike B exception queue: story, matched $, pending HITL, time-to-approve.

    Read-only. Does not apply matches or open approvals.
    """
    try:
        _guard("ar_exception_queue_summary")
    except CircuitOpenError as exc:
        return {"status": "circuit_open", "error": str(exc), "needs_review": True}

    snapshot = build_ar_exception_queue()
    if include_markdown:
        from finance_ops.runtime.exception_queue import format_queue_markdown

        snapshot["markdown"] = format_queue_markdown(snapshot)

    metrics = snapshot.get("metrics") or {}
    snapshot["evidence"] = record_evidence(
        agent="finance_ops_coordinator",
        action="ar_exception_queue_summary",
        inputs={"include_markdown": include_markdown},
        outputs={
            "matched_usd": metrics.get("matched_usd"),
            "open_exception_usd": metrics.get("open_exception_usd"),
            "pending_approvals": metrics.get("pending_approvals"),
            "tta_count": (metrics.get("time_to_approve_seconds") or {}).get("count"),
        },
        sources=["queue:spike_a+spike_b", "hitl:approval_store"],
    )
    return snapshot


def sync_ar_exceptions() -> dict[str, Any]:
    """Materialise ar_exceptions projection from warehouse (product queue)."""
    try:
        _guard("sync_ar_exceptions")
    except CircuitOpenError as exc:
        return {"status": "circuit_open", "error": str(exc), "needs_review": True}

    from finance_ops.services.queue_service import sync_from_warehouse

    out = sync_from_warehouse()
    out["evidence"] = record_evidence(
        agent="finance_ops_coordinator",
        action="sync_ar_exceptions",
        inputs={},
        outputs={"synced_count": out.get("synced_count")},
        sources=["queue:ar_exceptions", "warehouse"],
    )
    return out


def ingest_ar_feed(stage_sample: bool = True, csv_path: str = "") -> dict[str, Any]:
    """Ingest ERP unmatched-payment CSV from drop zone (or bundled sample)."""
    try:
        _guard("ingest_ar_feed")
    except CircuitOpenError as exc:
        return {"status": "circuit_open", "error": str(exc), "needs_review": True}

    from finance_ops.runtime.ar_feed import ingest_erp_payment_csv, stage_sample_erp_feed

    if stage_sample and not (csv_path or "").strip():
        stage_sample_erp_feed()
    out = ingest_erp_payment_csv(csv_path.strip() or None)
    out["evidence"] = record_evidence(
        agent="finance_ops_coordinator",
        action="ingest_ar_feed",
        inputs={"stage_sample": stage_sample, "csv_path": csv_path or None},
        outputs={"count": out.get("count"), "status": out.get("status")},
        sources=["feed:erp_csv", "incoming:ar_exceptions"],
    )
    return out


def start_ar_exception_triage(
    stage_sample: bool = True,
    request_hitl: bool = False,
    notify_slack: bool = False,
    use_live_hubspot: bool = True,
) -> dict[str, Any]:
    """Slice 2 — durable feed → cash-app triage → HubSpot gaps → queue metrics.

    Does not apply matches. Set request_hitl=True to open Slack/HITL for
    high-confidence suggestions via request_cash_app_approval.
    """
    try:
        _guard("start_ar_exception_triage")
    except CircuitOpenError as exc:
        return {"status": "circuit_open", "error": str(exc), "needs_review": True}

    import uuid
    from datetime import datetime, timezone

    from finance_ops.runtime.durable import (
        DurableWorkflow,
        StepStatus,
        WorkflowState,
        WorkflowStep,
        ar_exception_triage_handlers,
    )

    handlers = ar_exception_triage_handlers()
    wf = DurableWorkflow()
    now = datetime.now(timezone.utc).isoformat()
    # Second-precision timestamps collide under concurrent/rapid runs and
    # overwrite durable checkpoints — always include a unique suffix.
    run_id = (
        f"WF-AR-TRIAGE-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-"
        f"{uuid.uuid4().hex[:10]}"
    )
    state = WorkflowState(
        run_id=run_id,
        name="ar_exception_triage",
        status=StepStatus.pending,
        steps=[WorkflowStep(name=n) for n in handlers.keys()],
        created_at=now,
        updated_at=now,
        meta={
            "stage_sample": bool(stage_sample),
            "request_hitl": bool(request_hitl),
            "notify_slack": bool(notify_slack),
            "use_live_hubspot": bool(use_live_hubspot),
            "source": "slice2_live_feed",
        },
    )
    wf.save(state)
    finished = wf.run(handlers, state=state, max_retries=2, base_delay_seconds=0.01)

    result = {
        "status": finished.status.value,
        "run_id": finished.run_id,
        "workflow_name": finished.name,
        "steps": [s.model_dump() for s in finished.steps],
        "feed_ingest": finished.meta.get("feed_ingest"),
        "cash_app_triage": {
            "payment_count": (finished.meta.get("cash_app_triage") or {}).get("payment_count"),
            "ready_count": (finished.meta.get("cash_app_triage") or {}).get("ready_count"),
            "ready_for_hitl": (finished.meta.get("cash_app_triage") or {}).get("ready_for_hitl"),
        },
        "hubspot_gaps": {
            "mode": (finished.meta.get("hubspot_gaps") or {}).get("mode"),
            "gap_count": (finished.meta.get("hubspot_gaps") or {}).get("gap_count"),
            "gaps": (finished.meta.get("hubspot_gaps") or {}).get("gaps"),
        },
        "hitl_opened": finished.meta.get("hitl_opened"),
        "exception_sync": finished.meta.get("exception_sync"),
        "queue_metrics": finished.meta.get("queue_metrics"),
        "queue_projection": finished.meta.get("queue_projection"),
        "needs_review": finished.status.value != "success"
        or bool((finished.meta.get("hubspot_gaps") or {}).get("needs_review"))
        or bool((finished.meta.get("cash_app_triage") or {}).get("ready_count")),
    }
    result["evidence"] = record_evidence(
        agent="finance_ops_coordinator",
        action="start_ar_exception_triage",
        inputs={
            "stage_sample": stage_sample,
            "request_hitl": request_hitl,
            "use_live_hubspot": use_live_hubspot,
        },
        outputs={
            "run_id": finished.run_id,
            "status": finished.status.value,
            "ready_count": (finished.meta.get("cash_app_triage") or {}).get("ready_count"),
            "gap_count": (finished.meta.get("hubspot_gaps") or {}).get("gap_count"),
        },
        sources=["feed:erp_csv", "feed:hubspot_gaps", "runtime:durable"],
    )
    return result
