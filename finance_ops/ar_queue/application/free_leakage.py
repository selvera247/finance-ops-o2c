"""Free sold-vs-invoiced leakage report (no apply / no ERP write)."""

from __future__ import annotations

from typing import Any


def _f(raw: Any) -> float:
    try:
        return float(raw or 0)
    except (TypeError, ValueError):
        return 0.0


def _gap_threshold(sold: float, invoiced: float) -> float:
    return max(500.0, 0.05 * max(sold, invoiced, 1.0))


def build_free_leakage_report(
    closed_won: list[dict[str, Any]],
    invoices: list[dict[str, Any]],
    *,
    company_name: str | None = None,
    top_n: int = 25,
) -> dict[str, Any]:
    """Compare CRM closed-won (sold) vs invoiced AR by customer_id.

    Free.visibility-style readout for revenue leakage — suggestions/classification only.
    """
    sold_by_cust: dict[str, dict[str, Any]] = {}
    for row in closed_won:
        cust = str(row.get("customer_id") or "").strip().upper()
        if not cust:
            continue
        amt = _f(row.get("sold") if row.get("sold") not in (None, "") else row.get("amount"))
        prev = sold_by_cust.get(cust)
        if prev is None:
            sold_by_cust[cust] = {
                "customer_id": cust,
                "company_name": row.get("company_name") or row.get("customer_name") or cust,
                "sold": amt,
                "deal_ids": [d for d in [row.get("deal_id")] if d],
                "deal_count": 1,
            }
        else:
            prev["sold"] = float(prev["sold"]) + amt
            prev["deal_count"] = int(prev["deal_count"]) + 1
            if row.get("deal_id"):
                prev["deal_ids"].append(row["deal_id"])
            if row.get("company_name") and prev["company_name"] == cust:
                prev["company_name"] = row["company_name"]

    inv_by_cust: dict[str, dict[str, float | int]] = {}
    for inv in invoices:
        cust = str(inv.get("customer_id") or "").strip().upper()
        if not cust:
            continue
        amt = _f(inv.get("amount"))
        status = str(inv.get("status") or "").lower()
        bucket = inv_by_cust.setdefault(
            cust, {"invoiced_total": 0.0, "open_invoiced": 0.0, "invoice_count": 0}
        )
        bucket["invoiced_total"] = float(bucket["invoiced_total"]) + amt
        bucket["invoice_count"] = int(bucket["invoice_count"]) + 1
        if status in {"open", "past_due", ""}:
            bucket["open_invoiced"] = float(bucket["open_invoiced"]) + amt

    customers = sorted(set(sold_by_cust) | set(inv_by_cust))
    gaps: list[dict[str, Any]] = []
    aligned: list[dict[str, Any]] = []

    for cust in customers:
        sold_row = sold_by_cust.get(cust) or {
            "customer_id": cust,
            "company_name": cust,
            "sold": 0.0,
            "deal_ids": [],
            "deal_count": 0,
        }
        inv_row = inv_by_cust.get(cust) or {
            "invoiced_total": 0.0,
            "open_invoiced": 0.0,
            "invoice_count": 0,
        }
        sold = float(sold_row["sold"])
        invoiced = float(inv_row["invoiced_total"])
        open_inv = float(inv_row["open_invoiced"])
        leakage = round(sold - invoiced, 2)
        detected: list[str] = []
        if sold and invoiced and abs(sold - invoiced) > _gap_threshold(sold, invoiced):
            detected.append("sold_vs_invoiced")
        if sold and open_inv > sold * 1.05:
            detected.append("open_ar_over_sold")
        if sold and not invoiced:
            detected.append("sold_without_invoices")
        if invoiced and not sold:
            detected.append("invoiced_without_closed_won")

        item = {
            "customer_id": cust,
            "company_name": sold_row.get("company_name") or cust,
            "sold": round(sold, 2),
            "invoiced_total": round(invoiced, 2),
            "open_invoiced": round(open_inv, 2),
            "leakage_usd": leakage,
            "gaps": detected,
            "deal_count": int(sold_row.get("deal_count") or 0),
            "invoice_count": int(inv_row.get("invoice_count") or 0),
            "deal_ids": list(sold_row.get("deal_ids") or [])[:10],
            "needs_review": bool(detected),
        }
        if detected:
            gaps.append(item)
        else:
            aligned.append(item)

    gaps.sort(key=lambda r: -abs(float(r.get("leakage_usd") or 0)))
    total_leakage = round(
        sum(max(float(g.get("leakage_usd") or 0), 0.0) for g in gaps), 2
    )
    total_sold = round(sum(float(s["sold"]) for s in sold_by_cust.values()), 2)
    total_invoiced = round(
        sum(float(i["invoiced_total"]) for i in inv_by_cust.values()), 2
    )

    summary = {
        "company_name": company_name or "Prospect",
        "customer_count": len(customers),
        "gap_customer_count": len(gaps),
        "aligned_customer_count": len(aligned),
        "total_sold_usd": total_sold,
        "total_invoiced_usd": total_invoiced,
        "positive_leakage_usd": total_leakage,
        "tier": "free.visibility",
        "lane": "sold_vs_invoiced",
        "cta": (
            "Free leakage visibility — nothing was invoiced or credited. "
            "Paid path: resolve gaps (invoice / credit ops) with human review."
        ),
    }
    report = {
        "status": "success",
        "summary": summary,
        "gaps": gaps[: max(1, int(top_n))],
        "aligned_sample": aligned[: min(5, len(aligned))],
        "needs_review": len(gaps) > 0,
        "sku": "free.visibility",
        "lane": "sold_vs_invoiced",
    }
    report["markdown"] = format_free_leakage_markdown(report)
    return report


def format_free_leakage_markdown(report: dict[str, Any]) -> str:
    s = report.get("summary") or {}
    company = s.get("company_name") or "Prospect"
    lines = [
        f"# Sold vs invoiced — free leakage readout ({company})",
        "",
        s.get("cta") or "",
        "",
        "## Snapshot",
        f"- Customers compared: **{s.get('customer_count', 0)}**",
        f"- Customers with gaps: **{s.get('gap_customer_count', 0)}**",
        f"- Closed-won (sold): **${s.get('total_sold_usd', 0):,.2f}**",
        f"- Invoiced: **${s.get('total_invoiced_usd', 0):,.2f}**",
        f"- Positive leakage (sold − invoiced, gaps only): "
        f"**${s.get('positive_leakage_usd', 0):,.2f}**",
        "",
        "## Gap customers (review)",
        "",
        "| Customer | Company | Sold | Invoiced | Leakage | Flags |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in report.get("gaps") or []:
        flags = ", ".join(row.get("gaps") or []) or "—"
        lines.append(
            f"| {row.get('customer_id')} | {row.get('company_name')} | "
            f"${float(row.get('sold') or 0):,.2f} | "
            f"${float(row.get('invoiced_total') or 0):,.2f} | "
            f"${float(row.get('leakage_usd') or 0):,.2f} | {flags} |"
        )
    if not report.get("gaps"):
        lines.append("| — | — | — | — | — | no material gaps |")

    lines.extend(
        [
            "",
            "---",
            "*Free tier: visibility only. "
            "To resolve leakage (invoice missing revenue or credit overbill): "
            "pilot / human-reviewed ops — not per-seat dashboards.*",
            "",
        ]
    )
    return "\n".join(lines)
