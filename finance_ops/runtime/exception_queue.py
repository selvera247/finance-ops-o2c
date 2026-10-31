"""AR exception queue — Spike A cash app + Spike B portal as one story + metrics.

No dashboard: JSON (and optional markdown) for agents, MCP, HTTP, and CLI.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any

from finance_ops.runtime.hitl import ApprovalStore, DEFAULT_STORE
from finance_ops.runtime.shadow import SPIKE_A_WALKTHROUGH, SPIKE_B_WALKTHROUGH

STORY = (
    "feed → triage → request_cash_app_approval / request_portal_extract_review "
    "→ Slack Approve/Reject → apply_payment_match (post-approve only)"
)

CASH_APP_KINDS = frozenset(
    {"cash_app_match", "cash_app_escalate", "payment_match", "cash_app"}
)
PORTAL_KINDS = frozenset(
    {
        "portal_claim_denied",
        "portal_claim_pending",
        "portal_orphan_cash",
        "portal_remittance_match",
        "portal_remittance_review",
        "portal_extract_review",
    }
)
QUEUE_KINDS = CASH_APP_KINDS | PORTAL_KINDS


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _amount(row: dict[str, Any]) -> float:
    try:
        return float(row.get("amount") or 0)
    except (TypeError, ValueError):
        return 0.0


def _percentile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 3)
    # Nearest-rank
    k = max(1, min(len(sorted_vals), int(round(p * len(sorted_vals)))))
    return round(sorted_vals[k - 1], 3)


def _time_to_approve_stats(approvals: list[Any]) -> dict[str, Any]:
    deltas: list[float] = []
    for item in approvals:
        if getattr(item, "status", None) != "approved":
            continue
        start = _parse_ts(getattr(item, "created_at", None))
        end = _parse_ts(getattr(item, "decided_at", None))
        if start is None or end is None:
            continue
        sec = (end - start).total_seconds()
        if sec >= 0:
            deltas.append(sec)
    deltas.sort()
    if not deltas:
        return {
            "count": 0,
            "mean_seconds": None,
            "median_seconds": None,
            "p95_seconds": None,
        }
    return {
        "count": len(deltas),
        "mean_seconds": round(statistics.fmean(deltas), 3),
        "median_seconds": round(statistics.median(deltas), 3),
        "p95_seconds": _percentile(deltas, 0.95),
    }


def _cash_app_lane() -> dict[str, Any]:
    from data_plane import repository as repo

    payments = repo.list_payments()
    matched = [p for p in payments if str(p.get("status") or "").lower() == "matched"]
    open_exc = [
        p
        for p in payments
        if str(p.get("status") or "").lower() in {"unmatched", "partial"}
    ]
    walkthrough = []
    for pid in SPIKE_A_WALKTHROUGH:
        row = next(
            (
                p
                for p in payments
                if str(p.get("payment_id") or "").upper() == pid
            ),
            None,
        )
        walkthrough.append(
            {
                "id": pid,
                "lane": "cash_app",
                "status": (row or {}).get("status", "missing"),
                "amount": _amount(row or {}),
                "matched_invoice_id": (row or {}).get("matched_invoice_id"),
                "stage": (
                    "applied"
                    if (row or {}).get("status") == "matched"
                    else "open_exception"
                ),
            }
        )
    return {
        "name": "cash_app",
        "spike": "A",
        "entry_tool": "request_cash_app_approval",
        "payment_count": len(payments),
        "matched_count": len(matched),
        "matched_usd": round(sum(_amount(p) for p in matched), 2),
        "open_exception_count": len(open_exc),
        "open_exception_usd": round(sum(_amount(p) for p in open_exc), 2),
        "walkthrough": walkthrough,
    }


def _portal_lane() -> dict[str, Any]:
    from finance_ops.ar_queue.adapters.warehouse_payments import (
        DEFAULT_PAYMENT_CATALOG,
    )
    from finance_ops.ar_queue.domain.portal_classify import classify_portal_row

    # One portal scan for all walkthrough ids (avoid N full-table searches).
    extracts = DEFAULT_PAYMENT_CATALOG.portal_extracts_by_external_id()
    items = []
    open_usd = 0.0
    accept_usd = 0.0
    for cid in SPIKE_B_WALKTHROUGH:
        classified = classify_portal_row(cid, extracts.get(cid))
        amount = float(classified.get("amount") or 0)
        disposition = classified.get("disposition")
        stage = (
            "ready_accept"
            if disposition == "accept_remittance"
            else "needs_hitl"
            if classified.get("status") == "success"
            else "missing_load"
        )
        if stage == "ready_accept":
            accept_usd += amount
        elif stage == "needs_hitl":
            open_usd += amount
        items.append(
            {
                "id": cid,
                "lane": "portal_remittance",
                "status": classified.get("status"),
                "disposition": disposition,
                "hitl_kind": classified.get("hitl_kind"),
                "amount": amount,
                "stage": stage,
                "suggested_invoice_ids": classified.get("suggested_invoice_ids") or [],
            }
        )
    return {
        "name": "portal_remittance",
        "spike": "B",
        "entry_tool": "request_portal_extract_review",
        "walkthrough_count": len(SPIKE_B_WALKTHROUGH),
        "open_exception_usd": round(open_usd, 2),
        "ready_accept_usd": round(accept_usd, 2),
        "walkthrough": items,
    }


def _approval_slice(store: ApprovalStore) -> dict[str, Any]:
    all_items = store.list(status=None)
    queue_items = [a for a in all_items if a.kind in QUEUE_KINDS]
    pending = [a for a in queue_items if a.status == "pending"]
    approved = [a for a in queue_items if a.status == "approved"]
    rejected = [a for a in queue_items if a.status == "rejected"]
    by_lane = {
        "cash_app_pending": sum(1 for a in pending if a.kind in CASH_APP_KINDS),
        "portal_pending": sum(1 for a in pending if a.kind in PORTAL_KINDS),
    }
    return {
        "pending_count": len(pending),
        "pending_usd": round(sum(float(a.amount or 0) for a in pending), 2),
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "by_lane": by_lane,
        "time_to_approve": _time_to_approve_stats(queue_items),
        "pending": [
            {
                "approval_id": a.approval_id,
                "kind": a.kind,
                "amount": a.amount,
                "summary": a.summary,
                "created_at": a.created_at,
                "lane": "cash_app" if a.kind in CASH_APP_KINDS else "portal_remittance",
            }
            for a in pending
        ],
    }


def build_ar_exception_queue(
    *,
    store: ApprovalStore | None = None,
) -> dict[str, Any]:
    """Aggregate Spike A + Spike B into one exception-queue snapshot."""
    hitl = _approval_slice(store or DEFAULT_STORE)
    cash = _cash_app_lane()
    portal = _portal_lane()

    open_items = [
        *[{**w, "source": "spike_a"} for w in cash["walkthrough"] if w["stage"] == "open_exception"],
        *[
            {**w, "source": "spike_b"}
            for w in portal["walkthrough"]
            if w["stage"] in {"needs_hitl", "missing_load"}
        ],
    ]

    metrics = {
        "matched_usd": cash["matched_usd"],
        "matched_count": cash["matched_count"],
        "open_exception_usd": round(
            cash["open_exception_usd"] + portal["open_exception_usd"], 2
        ),
        "pending_approvals": hitl["pending_count"],
        "pending_approval_usd": hitl["pending_usd"],
        "time_to_approve_seconds": hitl["time_to_approve"],
    }

    return {
        "status": "success",
        "story": STORY,
        "non_goals": [
            "per-seat dashboard chrome",
            "silent auto-write-off",
            "direct apply_payment_match as agent entry",
        ],
        "lanes": {"cash_app": cash, "portal_remittance": portal},
        "hitl": hitl,
        "metrics": metrics,
        "open_exceptions": open_items,
        "needs_review": metrics["pending_approvals"] > 0 or len(open_items) > 0,
    }


def _fmt_sec(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value}s"


def format_queue_markdown(snapshot: dict[str, Any]) -> str:
    """Plain markdown narrative for CLI / Slack paste — not a UI."""
    m = snapshot.get("metrics") or {}
    tta = m.get("time_to_approve_seconds") or {}
    lines = [
        "# AR exception queue",
        "",
        f"**Story:** {snapshot.get('story')}",
        "",
        "## Metrics",
        f"- Matched: **${m.get('matched_usd', 0):,.2f}** ({m.get('matched_count', 0)} payments)",
        f"- Open exceptions: **${m.get('open_exception_usd', 0):,.2f}**",
        f"- Pending approvals: **{m.get('pending_approvals', 0)}** "
        f"(${m.get('pending_approval_usd', 0):,.2f})",
        (
            f"- Time-to-approve: n={tta.get('count', 0)}, "
            f"median={_fmt_sec(tta.get('median_seconds'))}, "
            f"mean={_fmt_sec(tta.get('mean_seconds'))}, "
            f"p95={_fmt_sec(tta.get('p95_seconds'))}"
        ),
        "",
        "## Lanes",
    ]
    cash = (snapshot.get("lanes") or {}).get("cash_app") or {}
    portal = (snapshot.get("lanes") or {}).get("portal_remittance") or {}
    lines.append(
        f"- Cash app (Spike A): open ${cash.get('open_exception_usd', 0):,.2f} · "
        f"entry `{cash.get('entry_tool')}`"
    )
    lines.append(
        f"- Portal remittance (Spike B): open ${portal.get('open_exception_usd', 0):,.2f} · "
        f"entry `{portal.get('entry_tool')}`"
    )
    open_exc = snapshot.get("open_exceptions") or []
    if open_exc:
        lines.extend(["", "## Open walkthrough items"])
        for item in open_exc:
            lines.append(
                f"- `{item.get('id')}` ({item.get('lane')}) "
                f"${item.get('amount', 0):,.2f} · {item.get('stage')}"
            )
    pending = (snapshot.get("hitl") or {}).get("pending") or []
    if pending:
        lines.extend(["", "## Pending HITL"])
        for a in pending:
            lines.append(
                f"- `{a.get('approval_id')}` {a.get('kind')} "
                f"${a.get('amount', 0):,.2f} — {a.get('summary')}"
            )
    return "\n".join(lines) + "\n"
