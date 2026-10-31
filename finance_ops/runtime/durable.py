"""#1 Durable state-machine workflow (Temporal/LangGraph-shaped, file checkpoints).

Runs a multi-step portal extract → ingest → reconcile DAG with:
  - persisted checkpoints
  - exponential backoff retries
  - crash recovery via resume(run_id)
"""

from __future__ import annotations

import json
import time
import traceback
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from data_plane.config import WAREHOUSE_DIR, ensure_dirs


class StepStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    skipped = "skipped"


class WorkflowStep(BaseModel):
    name: str
    status: StepStatus = StepStatus.pending
    attempts: int = 0
    last_error: str | None = None
    output: dict[str, Any] = Field(default_factory=dict)
    started_at: str | None = None
    finished_at: str | None = None


class WorkflowState(BaseModel):
    run_id: str
    name: str = "portal_extract_reconcile"
    status: StepStatus = StepStatus.pending
    steps: list[WorkflowStep]
    created_at: str
    updated_at: str
    meta: dict[str, Any] = Field(default_factory=dict)


StepFn = Callable[[WorkflowState], dict[str, Any]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DurableWorkflow:
    def __init__(self, root: Path | None = None) -> None:
        ensure_dirs()
        self.root = root or (WAREHOUSE_DIR / "workflows")
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        return self.root / f"{run_id}.json"

    def save(self, state: WorkflowState) -> None:
        state.updated_at = _now()
        self._path(state.run_id).write_text(state.model_dump_json(indent=2), encoding="utf-8")

    def load(self, run_id: str) -> WorkflowState:
        return WorkflowState.model_validate_json(self._path(run_id).read_text(encoding="utf-8"))

    def create(self, step_names: list[str], *, meta: dict[str, Any] | None = None) -> WorkflowState:
        state = WorkflowState(
            run_id=f"WF-{uuid.uuid4().hex[:10]}",
            steps=[WorkflowStep(name=n) for n in step_names],
            created_at=_now(),
            updated_at=_now(),
            meta=meta or {},
        )
        self.save(state)
        return state

    def run(
        self,
        handlers: dict[str, StepFn],
        *,
        state: WorkflowState | None = None,
        max_retries: int = 3,
        base_delay_seconds: float = 0.05,
    ) -> WorkflowState:
        if state is None:
            state = self.create(list(handlers.keys()))
        state.status = StepStatus.running
        self.save(state)

        for step in state.steps:
            if step.status == StepStatus.success:
                continue
            fn = handlers[step.name]
            while step.attempts < max_retries:
                step.attempts += 1
                step.status = StepStatus.running
                step.started_at = step.started_at or _now()
                step.last_error = None
                self.save(state)
                try:
                    step.output = fn(state) or {}
                    step.status = StepStatus.success
                    step.finished_at = _now()
                    self.save(state)
                    break
                except Exception as exc:  # noqa: BLE001
                    step.last_error = f"{exc}\n{traceback.format_exc(limit=3)}"
                    self.save(state)
                    if step.attempts >= max_retries:
                        step.status = StepStatus.failed
                        step.finished_at = _now()
                        state.status = StepStatus.failed
                        self.save(state)
                        return state
                    time.sleep(base_delay_seconds * (2 ** (step.attempts - 1)))

        if all(s.status == StepStatus.success for s in state.steps):
            state.status = StepStatus.success
        self.save(state)
        return state

    def resume(self, run_id: str, handlers: dict[str, StepFn], **kwargs: Any) -> WorkflowState:
        state = self.load(run_id)
        return self.run(handlers, state=state, **kwargs)

    def signal(self, run_id: str, name: str, payload: dict[str, Any] | None = None) -> WorkflowState:
        """Temporal-shaped external signal (e.g. HITL approved) persisted on meta."""
        state = self.load(run_id)
        signals = list(state.meta.get("signals") or [])
        signals.append({"name": name, "payload": payload or {}, "at": _now()})
        state.meta["signals"] = signals
        state.meta[f"signal_{name}"] = payload or {"ok": True}
        self.save(state)
        return state


def portal_reconcile_handlers() -> dict[str, StepFn]:
    """Default DAG: ensure warehouse → process incoming → fallback resolve → smoke match."""

    def step_batch(state: WorkflowState) -> dict[str, Any]:
        from pipelines.batch.ingest import ingest_batch

        return ingest_batch(run_id=f"wf-batch-{state.run_id}")

    def step_incoming(state: WorkflowState) -> dict[str, Any]:
        from gui_connectors.ingest.portal_ingest import process_incoming

        return process_incoming()

    def step_resolve(state: WorkflowState) -> dict[str, Any]:
        from finance_ops.runtime.fallback_router import resolve_portal_data

        return resolve_portal_data(
            "legacy_bank",
            extract_type="bank_statement",
            min_rows=1,
            allow_browser_fallback=bool(state.meta.get("allow_browser", True)),
        )

    def step_reconcile_smoke(state: WorkflowState) -> dict[str, Any]:
        from finance_ops.tools.payment_tools import suggest_payment_match

        return suggest_payment_match("PAY-9002")

    return {
        "batch_ingest": step_batch,
        "process_incoming": step_incoming,
        "resolve_portal": step_resolve,
        "reconcile_smoke": step_reconcile_smoke,
    }


def deal_closed_won_handlers() -> dict[str, StepFn]:
    """D7 DAG keyed by HubSpot deal id: fetch deal → line items → flag review."""

    def step_fetch_deal(state: WorkflowState) -> dict[str, Any]:
        from finance_ops.tools.hubspot_tools import get_deal

        deal_id = str(state.meta.get("hubspot_deal_id") or "")
        out = get_deal(deal_id)
        if out.get("status") != "success":
            raise RuntimeError(out.get("error") or "hubspot_get_deal_failed")
        state.meta["deal"] = out.get("deal") or {}
        return {"deal_id": deal_id, "status": out.get("status")}

    def step_line_items(state: WorkflowState) -> dict[str, Any]:
        from finance_ops.tools.hubspot_tools import get_deal_line_items

        deal_id = str(state.meta.get("hubspot_deal_id") or "")
        out = get_deal_line_items(deal_id)
        if out.get("status") not in {"success", "denied"}:
            # denied (no token) soft-records; other errors retry
            if out.get("status") == "error":
                raise RuntimeError(out.get("error") or "line_items_failed")
        state.meta["line_items"] = out.get("line_items") or []
        return {"count": out.get("count", 0), "status": out.get("status")}

    def step_flag_review(state: WorkflowState) -> dict[str, Any]:
        deal = state.meta.get("deal") or {}
        props = deal.get("properties") if isinstance(deal, dict) else {}
        amount = props.get("amount") if isinstance(props, dict) else None
        return {
            "needs_review": True,
            "reason": "hubspot_deal_closed_won_review",
            "deal_id": state.meta.get("hubspot_deal_id"),
            "amount": amount,
            "line_item_count": len(state.meta.get("line_items") or []),
        }

    return {
        "fetch_deal": step_fetch_deal,
        "fetch_line_items": step_line_items,
        "flag_review": step_flag_review,
    }


def ar_exception_triage_handlers() -> dict[str, StepFn]:
    """Slice 2 DAG: ERP/HubSpot feed → triage suggestions → optional HITL → queue metrics.

    Never applies payment matches. HITL open is opt-in via meta.request_hitl.
    """

    def step_ingest_feed(state: WorkflowState) -> dict[str, Any]:
        from finance_ops.runtime.ar_feed import ingest_erp_payment_csv, stage_sample_erp_feed

        # Explicit stage only — ingest never auto-restages demo CSV in prod.
        if state.meta.get("stage_sample", True):
            staged = stage_sample_erp_feed()
            state.meta["feed_staged"] = staged
        path = state.meta.get("erp_csv_path")
        out = ingest_erp_payment_csv(
            path, auto_stage_sample=False
        )
        if out.get("status") != "success":
            raise RuntimeError(out.get("error") or "erp_feed_ingest_failed")
        state.meta["feed_ingest"] = out
        return {
            "count": out.get("count"),
            "payment_ids": out.get("payment_ids"),
            "row_error_count": len(out.get("row_errors") or []),
        }

    def step_triage_cash_app(state: WorkflowState) -> dict[str, Any]:
        from finance_ops.runtime.ar_feed import triage_unmatched_payments

        payment_ids = (state.meta.get("feed_ingest") or {}).get("payment_ids")
        out = triage_unmatched_payments(payment_ids=payment_ids)
        state.meta["cash_app_triage"] = out
        return {
            "payment_count": out.get("payment_count"),
            "ready_count": out.get("ready_count"),
        }

    def step_triage_hubspot_gaps(state: WorkflowState) -> dict[str, Any]:
        from data_plane import repository as repo
        from finance_ops.runtime.ar_feed import triage_hubspot_gaps

        feed_ids = (state.meta.get("feed_ingest") or {}).get("payment_ids") or []
        customers: list[str] = []
        for pid in feed_ids:
            row = repo.get_payment(str(pid))
            if row and row.get("customer_id"):
                customers.append(str(row["customer_id"]).upper())
        customer_ids = sorted(set(customers)) or None
        out = triage_hubspot_gaps(
            customer_ids=customer_ids,
            use_live_hubspot=bool(state.meta.get("use_live_hubspot", True)),
        )
        state.meta["hubspot_gaps"] = out
        return {"gap_count": out.get("gap_count"), "mode": out.get("mode")}

    def step_optional_hitl(state: WorkflowState) -> dict[str, Any]:
        if not state.meta.get("request_hitl"):
            return {"skipped": True, "opened_count": 0}
        from finance_ops.runtime.ar_feed import open_hitl_for_ready
        from finance_ops.services.queue_service import mark_pending_hitl

        ready = (state.meta.get("cash_app_triage") or {}).get("ready_for_hitl") or []
        out = open_hitl_for_ready(
            ready,
            notify_slack=bool(state.meta.get("notify_slack", False)),
        )
        for opened in out.get("opened") or []:
            if opened.get("status") == "pending" and opened.get("approval_id"):
                mark_pending_hitl(
                    source_id=str(opened.get("payment_id") or ""),
                    lane="cash_app",
                    approval_id=str(opened["approval_id"]),
                )
        state.meta["hitl_opened"] = out
        return out

    def step_sync_exceptions(state: WorkflowState) -> dict[str, Any]:
        from finance_ops.services.queue_service import sync_from_warehouse

        payment_ids = (state.meta.get("feed_ingest") or {}).get("payment_ids")
        out = sync_from_warehouse(
            workflow_run_id=state.run_id,
            payment_ids=payment_ids,
            include_portal=True,
            include_hubspot_gaps=True,
        )
        state.meta["exception_sync"] = out
        return {
            "synced_count": out.get("synced_count"),
            "hubspot_gap_count": out.get("hubspot_gap_count"),
        }

    def step_queue_snapshot(state: WorkflowState) -> dict[str, Any]:
        from finance_ops.services.queue_service import queue_metrics

        metrics_full = queue_metrics(use_cache=False)
        metrics = metrics_full.get("legacy_metrics") or {}
        state.meta["queue_metrics"] = metrics
        state.meta["queue_projection"] = metrics_full.get("projection")
        return {
            "matched_usd": metrics.get("matched_usd"),
            "open_exception_usd": (metrics_full.get("projection") or {}).get(
                "open_exception_usd"
            ),
            "pending_approvals": metrics.get("pending_approvals"),
            "exception_count": (metrics_full.get("projection") or {}).get(
                "exception_count"
            ),
            "needs_review": metrics_full.get("needs_review"),
        }

    return {
        "ingest_ar_feed": step_ingest_feed,
        "triage_cash_app": step_triage_cash_app,
        "triage_hubspot_gaps": step_triage_hubspot_gaps,
        # Sync before HITL so mark_pending_hitl updates existing queue rows.
        "sync_exceptions": step_sync_exceptions,
        "optional_hitl": step_optional_hitl,
        "queue_snapshot": step_queue_snapshot,
    }
