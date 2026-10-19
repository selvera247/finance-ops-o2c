"""Agent-callable wrappers for runtime gaps (#11/#12/#8/#1/#5)."""

from __future__ import annotations

from typing import Any

from finance_ops.lib.evidence import record_evidence
from finance_ops.runtime.circuit_breaker import DEFAULT_BREAKER, CircuitOpenError
from finance_ops.runtime.hitl import DEFAULT_STORE


def _guard(tool_name: str) -> None:
    DEFAULT_BREAKER.record_tool(tool_name)


def circuit_status() -> dict[str, Any]:
    """#12 Inspect circuit breaker budget (tool calls / depth)."""
    snap = DEFAULT_BREAKER.snapshot()
    return {"status": "success", "circuit": snap, "needs_review": snap.get("open", False)}


def reset_circuit_breaker() -> dict[str, Any]:
    """Reset process-wide circuit breaker (ops / eval only)."""
    DEFAULT_BREAKER.reset()
    return {"status": "success", "circuit": DEFAULT_BREAKER.snapshot(), "needs_review": False}


def resolve_portal_with_fallback(
    portal_id: str = "legacy_bank",
    entity_id: str | None = None,
    extract_type: str | None = None,
    allow_browser_fallback: bool = True,
) -> dict[str, Any]:
    """#11 Warehouse/API first; on miss/timeout spawn Playwright portal pull."""
    from finance_ops.runtime.fallback_router import resolve_portal_data

    try:
        result = resolve_portal_data(
            portal_id,
            entity_id=entity_id,
            extract_type=extract_type,
            allow_browser_fallback=allow_browser_fallback,
        )
    except CircuitOpenError as exc:
        return {
            "status": "circuit_open",
            "error": str(exc),
            "circuit": DEFAULT_BREAKER.snapshot(),
            "needs_review": True,
        }
    result["evidence"] = record_evidence(
        agent="coordinator",
        action="resolve_portal_with_fallback",
        inputs={
            "portal_id": portal_id,
            "entity_id": entity_id,
            "extract_type": extract_type,
            "allow_browser_fallback": allow_browser_fallback,
        },
        outputs={
            "path": result.get("path"),
            "count": result.get("count"),
            "status": result.get("status"),
        },
        sources=[f"portal:{portal_id}", f"path:{result.get('path')}"],
    )
    return result


def request_approval(
    kind: str,
    amount: float,
    summary: str,
    related_ids: str = "",
    wait_days: float = 3.0,
) -> dict[str, Any]:
    """#8 Serialize a pending HITL approval (Slack/webhook resume stub)."""
    _guard("request_approval")
    payload = {
        "related_ids": [x.strip() for x in related_ids.split(",") if x.strip()],
    }
    approval = DEFAULT_STORE.create(
        kind=kind,
        amount=float(amount),
        summary=summary,
        payload=payload,
        wait_days=float(wait_days),
    )
    result = {
        "status": "pending",
        "approval": approval.model_dump(),
        "resume_hint": (
            f"Approve via HITL stub: python -m finance_ops.runtime.hitl_server "
            f"then open /approve?id={approval.approval_id}&token={approval.resume_token}"
        ),
        "needs_review": True,
    }
    result["evidence"] = record_evidence(
        agent="coordinator",
        action="request_approval",
        inputs={"kind": kind, "amount": amount, "summary": summary},
        outputs={"approval_id": approval.approval_id, "status": "pending"},
        sources=["hitl:approval_store"],
    )
    return result


def list_pending_approvals() -> dict[str, Any]:
    """List pending HITL approvals waiting for human decision."""
    _guard("list_pending_approvals")
    rows = [a.model_dump() for a in DEFAULT_STORE.list("pending")]
    return {
        "status": "success",
        "count": len(rows),
        "approvals": rows,
        "needs_review": len(rows) > 0,
    }


def decide_approval(
    approval_id: str,
    decision: str,
    resume_token: str = "",
    actor: str = "human",
) -> dict[str, Any]:
    """Resume after HITL: approve or reject a pending gate."""
    _guard("decide_approval")
    decision_norm = decision.strip().lower()
    if decision_norm not in {"approved", "rejected"}:
        return {
            "status": "error",
            "error": "decision must be approved|rejected",
            "needs_review": True,
        }
    try:
        item = DEFAULT_STORE.decide(
            approval_id,
            decision=decision_norm,  # type: ignore[arg-type]
            actor=actor,
            resume_token=resume_token or None,
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "needs_review": True}
    result = {
        "status": item.status,
        "approval": item.model_dump(),
        "needs_review": item.status != "approved",
    }
    result["evidence"] = record_evidence(
        agent="coordinator",
        action="decide_approval",
        inputs={"approval_id": approval_id, "decision": decision_norm, "actor": actor},
        outputs={"status": item.status},
        sources=["hitl:approval_store"],
    )
    return result


def start_durable_reconcile(allow_browser: bool = True) -> dict[str, Any]:
    """#1 Start checkpointed portal extract → reconcile DAG (crash-safe resume)."""
    _guard("start_durable_reconcile")
    from finance_ops.runtime.durable import DurableWorkflow, portal_reconcile_handlers

    wf = DurableWorkflow()
    state = wf.create(
        list(portal_reconcile_handlers().keys()),
        meta={"allow_browser": bool(allow_browser)},
    )
    # Run without browser in agent path by default for speed; caller can opt in.
    handlers = portal_reconcile_handlers()
    finished = wf.run(handlers, state=state, max_retries=2, base_delay_seconds=0.01)
    result = {
        "status": finished.status.value,
        "run_id": finished.run_id,
        "steps": [s.model_dump() for s in finished.steps],
        "needs_review": finished.status.value != "success",
    }
    result["evidence"] = record_evidence(
        agent="coordinator",
        action="start_durable_reconcile",
        inputs={"allow_browser": allow_browser},
        outputs={"run_id": finished.run_id, "status": finished.status.value},
        sources=["runtime:durable"],
    )
    return result


def resume_durable_workflow(run_id: str) -> dict[str, Any]:
    """Resume a durable workflow from its last checkpoint."""
    _guard("resume_durable_workflow")
    from finance_ops.runtime.durable import DurableWorkflow, portal_reconcile_handlers

    wf = DurableWorkflow()
    try:
        finished = wf.resume(run_id, portal_reconcile_handlers(), max_retries=2)
    except FileNotFoundError:
        return {"status": "not_found", "run_id": run_id, "needs_review": True}
    return {
        "status": finished.status.value,
        "run_id": finished.run_id,
        "steps": [s.model_dump() for s in finished.steps],
        "needs_review": finished.status.value != "success",
    }


def get_workflow_status(run_id: str) -> dict[str, Any]:
    """Load durable workflow checkpoint by run_id."""
    _guard("get_workflow_status")
    from finance_ops.runtime.durable import DurableWorkflow

    wf = DurableWorkflow()
    try:
        state = wf.load(run_id)
    except FileNotFoundError:
        return {"status": "not_found", "run_id": run_id, "needs_review": True}
    return {
        "status": "success",
        "workflow": state.model_dump(),
        "needs_review": state.status.value not in {"success", "pending"},
    }


def run_typed_a2a_aging(customer_id: str, conversation_id: str = "conv-local") -> dict[str, Any]:
    """#5 Typed A2A handoff: coordinator task → invoice specialist → typed result."""
    _guard("run_typed_a2a_aging")
    from finance_ops.runtime.a2a import (
        build_invoice_aging_task,
        execute_typed_invoice_aging,
    )

    state, task = build_invoice_aging_task(conversation_id, customer_id)
    result = execute_typed_invoice_aging(task)
    state.complete(result)
    payload = {
        "status": "success" if result.status != "error" else "error",
        "task": task.model_dump(),
        "result": result.model_dump(),
        "swarm": state.model_dump(),
        "needs_review": result.status == "needs_review",
    }
    payload["evidence"] = record_evidence(
        agent="coordinator",
        action="run_typed_a2a_aging",
        inputs={"customer_id": customer_id, "conversation_id": conversation_id},
        outputs={"task_id": task.task_id, "result_status": result.status},
        sources=["a2a:invoice_agent", f"customer:{customer_id}"],
    )
    return payload
