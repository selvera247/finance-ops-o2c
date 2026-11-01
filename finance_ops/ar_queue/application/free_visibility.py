"""Free visibility report — unmatched payments + open AR → suggestions (no apply)."""

from __future__ import annotations

from typing import Any

from finance_ops.ar_queue.domain.matching import score_payments_batch_cpu


def _f(raw: Any) -> float:
    try:
        return float(raw or 0)
    except (TypeError, ValueError):
        return 0.0


def build_free_visibility_report(
    payments: list[dict[str, Any]],
    invoices: list[dict[str, Any]],
    *,
    company_name: str | None = None,
    top_n: int = 15,
) -> dict[str, Any]:
    """Score unmatched cash against open invoices; return JSON + email markdown.

    Never applies matches or opens HITL — free.visibility only.
    """
    open_invoices = [
        inv
        for inv in invoices
        if str(inv.get("status") or "open").lower() in {"open", "past_due", ""}
    ]
    by_cust: dict[str, list[dict[str, Any]]] = {}
    for inv in open_invoices:
        by_cust.setdefault(str(inv.get("customer_id") or ""), []).append(inv)

    unmatched = [
        p
        for p in payments
        if str(p.get("status") or "unmatched").lower() in {"unmatched", "partial", ""}
    ]
    scored = score_payments_batch_cpu(unmatched, by_cust)

    suggestions: list[dict[str, Any]] = []
    orphans: list[dict[str, Any]] = []
    for pay in unmatched:
        pid = str(pay.get("payment_id") or "").strip().upper()
        if not pid:
            continue
        out = scored.get(pid) or {}
        cands = out.get("candidates") or []
        top = cands[0] if cands else None
        amount = _f(pay.get("amount"))
        item = {
            "payment_id": pid,
            "customer_id": pay.get("customer_id"),
            "amount": amount,
            "currency": pay.get("currency") or "USD",
            "reference": pay.get("reference") or "",
            "recommendation": out.get("recommendation"),
            "top_score": float((top or {}).get("score") or 0),
            "top_reasons": list((top or {}).get("reasons") or []),
            "candidate_count": len(cands),
        }
        if item["recommendation"]:
            suggestions.append(item)
        else:
            orphans.append(item)

    suggestions.sort(key=lambda r: (-r["top_score"], -r["amount"]))
    orphans.sort(key=lambda r: -r["amount"])

    open_payment_usd = round(sum(_f(p.get("amount")) for p in unmatched), 2)
    open_invoice_usd = round(sum(_f(i.get("amount")) for i in open_invoices), 2)
    suggested_usd = round(sum(s["amount"] for s in suggestions), 2)

    summary = {
        "company_name": company_name or "Prospect",
        "unmatched_payment_count": len(unmatched),
        "open_invoice_count": len(open_invoices),
        "open_unmatched_usd": open_payment_usd,
        "open_ar_usd": open_invoice_usd,
        "suggested_match_count": len(suggestions),
        "suggested_match_usd": suggested_usd,
        "orphan_payment_count": len(orphans),
        "tier": "free.visibility",
        "cta": (
            "Suggestions only — nothing was applied. "
            "Upgrade to resolve.cash_app (Slack Approve) to clear matches."
        ),
    }

    report = {
        "status": "success",
        "summary": summary,
        "suggestions": suggestions[: max(1, int(top_n))],
        "orphans": orphans[: max(1, int(top_n))],
        "needs_review": len(unmatched) > 0,
        "sku": "free.visibility",
    }
    report["markdown"] = format_free_visibility_markdown(report)
    return report


def format_free_visibility_markdown(report: dict[str, Any]) -> str:
    """Email-ready markdown for the free visibility readout."""
    s = report.get("summary") or {}
    company = s.get("company_name") or "Prospect"
    lines = [
        f"# AR exception queue — free visibility ({company})",
        "",
        s.get("cta") or "",
        "",
        "## Snapshot",
        f"- Unmatched payments: **{s.get('unmatched_payment_count', 0)}** "
        f"(${s.get('open_unmatched_usd', 0):,.2f})",
        f"- Open AR invoices: **{s.get('open_invoice_count', 0)}** "
        f"(${s.get('open_ar_usd', 0):,.2f})",
        f"- Suggested matches: **{s.get('suggested_match_count', 0)}** "
        f"(${s.get('suggested_match_usd', 0):,.2f})",
        f"- No-match orphans: **{s.get('orphan_payment_count', 0)}**",
        "",
        "## Top suggested matches",
        "",
        "| Payment | Customer | Amount | Suggested invoice | Score | Why |",
        "| --- | --- | ---: | --- | ---: | --- |",
    ]
    for row in report.get("suggestions") or []:
        reasons = ", ".join(row.get("top_reasons") or []) or "—"
        lines.append(
            f"| {row.get('payment_id')} | {row.get('customer_id')} | "
            f"${float(row.get('amount') or 0):,.2f} | {row.get('recommendation')} | "
            f"{row.get('top_score')} | {reasons} |"
        )
    if not report.get("suggestions"):
        lines.append("| — | — | — | — | — | no suggestions |")

    lines.extend(["", "## Orphan cash (no invoice candidate)", ""])
    for row in report.get("orphans") or []:
        lines.append(
            f"- **{row.get('payment_id')}** ({row.get('customer_id')}) "
            f"${float(row.get('amount') or 0):,.2f} — ref: {row.get('reference') or '—'}"
        )
    if not report.get("orphans"):
        lines.append("- None in this drop.")

    lines.extend(
        [
            "",
            "---",
            "*Free tier: visibility + suggestions only. "
            "To clear exceptions: pilot / resolve.cash_app (HITL Approve → apply).*",
            "",
        ]
    )
    return "\n".join(lines)
