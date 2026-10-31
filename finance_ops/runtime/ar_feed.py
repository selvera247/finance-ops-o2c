"""Slice 2 — live AR feed ingest (ERP CSV + HubSpot sold-vs-invoiced gaps).

Feeds land in the warehouse / triage meta. Apply still requires HITL via
request_cash_app_approval — this module never writes payment matches.
"""

from __future__ import annotations

import csv
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_plane.config import DATA_DIR, INCOMING_DIR, REPO_ROOT, ensure_dirs

AR_FEED_DIR = DATA_DIR / "ar_feed"
AR_INCOMING = INCOMING_DIR / "ar_exceptions"
SAMPLE_ERP_CSV = AR_FEED_DIR / "erp_unmatched_payments.csv"
SAMPLE_HUBSPOT_GAPS = AR_FEED_DIR / "hubspot_gaps.json"

# Require invoice reference + amount tolerance before auto-opening HITL.
# invoice_id_in_reference (0.7) + amount_within_tolerance (0.5) = 1.2
# invoice+PO alone (1.1) must NOT qualify — amount gate is mandatory.
HIGH_CONFIDENCE_SCORE = 1.0
REQUIRED_HITL_REASONS = frozenset({"invoice_id_in_reference", "amount_within_tolerance"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def stage_sample_erp_feed(*, dest_name: str = "erp_unmatched_payments.csv") -> dict[str, Any]:
    """Copy bundled sample ERP CSV into the ar_exceptions drop zone."""
    ensure_dirs()
    AR_INCOMING.mkdir(parents=True, exist_ok=True)
    if not SAMPLE_ERP_CSV.is_file():
        return {"status": "error", "error": f"missing sample {SAMPLE_ERP_CSV}"}
    dest = AR_INCOMING / dest_name
    shutil.copy2(SAMPLE_ERP_CSV, dest)
    return {"status": "success", "staged": str(dest), "source": str(SAMPLE_ERP_CSV)}


def _parse_amount(raw: Any) -> float | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def ingest_erp_payment_csv(
    path: str | Path | None = None,
    *,
    auto_stage_sample: bool = False,
) -> dict[str, Any]:
    """Upsert unmatched/partial payments from an ERP-shaped CSV into DuckDB.

    Production note: does **not** auto-stage the demo sample unless
    ``auto_stage_sample=True``. Callers that want the bundled sample must
    invoke ``stage_sample_erp_feed()`` explicitly (durable triage does this
    when ``meta.stage_sample`` is set).
    """
    from data_plane.warehouse import db

    ensure_dirs()
    db.init_schema()

    files: list[Path] = []
    if path:
        p = Path(path)
        if not p.is_file():
            return {"status": "error", "error": f"file not found: {p}"}
        files = [p]
    else:
        AR_INCOMING.mkdir(parents=True, exist_ok=True)
        files = sorted(
            f
            for f in AR_INCOMING.glob("*.csv")
            if f.is_file() and "processed" not in f.parts
        )
        if not files and auto_stage_sample and SAMPLE_ERP_CSV.is_file():
            stage_sample_erp_feed()
            files = [AR_INCOMING / "erp_unmatched_payments.csv"]

    if not files:
        return {
            "status": "error",
            "error": "no CSV in data/incoming/ar_exceptions/",
            "hint": "Drop an ERP export or call stage_sample_erp_feed() first",
            "payment_ids": [],
            "count": 0,
            "row_errors": [],
            "needs_review": True,
        }

    now = _now()
    upserted: list[str] = []
    row_errors: list[dict[str, Any]] = []
    processed_dir = AR_INCOMING / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%dT%H%M%S")
    uniq = uuid.uuid4().hex[:8]

    con = db.connect()
    try:
        for file_path in files:
            try:
                rows = _read_csv(file_path)
            except Exception as exc:  # noqa: BLE001
                row_errors.append(
                    {
                        "file": str(file_path),
                        "row": None,
                        "error": f"csv_read_failed:{exc}",
                    }
                )
                continue

            for idx, row in enumerate(rows, start=2):  # header = line 1
                pay_id = (row.get("payment_id") or "").strip().upper()
                if not pay_id:
                    row_errors.append(
                        {
                            "file": file_path.name,
                            "row": idx,
                            "error": "missing_payment_id",
                        }
                    )
                    continue
                cust = (row.get("customer_id") or "").strip()
                if not cust:
                    row_errors.append(
                        {
                            "file": file_path.name,
                            "row": idx,
                            "payment_id": pay_id,
                            "error": "missing_customer_id",
                        }
                    )
                    continue
                amount = _parse_amount(row.get("amount"))
                if amount is None:
                    row_errors.append(
                        {
                            "file": file_path.name,
                            "row": idx,
                            "payment_id": pay_id,
                            "error": "invalid_amount",
                            "raw": row.get("amount"),
                        }
                    )
                    continue
                currency = (row.get("currency") or "USD").strip() or "USD"
                status = (row.get("status") or "unmatched").strip().lower()
                if status not in {"unmatched", "partial", "matched"}:
                    status = "unmatched"
                reference = row.get("reference") or ""
                received = (
                    row.get("received_at") or row.get("payment_date") or now.date().isoformat()
                ).strip()
                try:
                    con.execute("DELETE FROM payments WHERE payment_id = ?", [pay_id])
                    con.execute(
                        "INSERT INTO payments VALUES (?,?,?,?,?,?,?,?,?,?)",
                        [
                            pay_id,
                            cust,
                            amount,
                            currency,
                            received,
                            "ACH",
                            reference,
                            None
                            if status != "matched"
                            else (row.get("matched_invoice_id") or None),
                            status,
                            now,
                        ],
                    )
                    upserted.append(pay_id)
                except Exception as exc:  # noqa: BLE001
                    row_errors.append(
                        {
                            "file": file_path.name,
                            "row": idx,
                            "payment_id": pay_id,
                            "error": f"db_upsert_failed:{exc}",
                        }
                    )

            # Move consumed drop-zone files aside (unique name avoids collisions).
            if file_path.parent.resolve() == AR_INCOMING.resolve():
                dest = processed_dir / f"{stamp}_{uniq}_{file_path.name}"
                try:
                    shutil.move(str(file_path), str(dest))
                except Exception as exc:  # noqa: BLE001
                    row_errors.append(
                        {
                            "file": file_path.name,
                            "row": None,
                            "error": f"archive_failed:{exc}",
                        }
                    )
    finally:
        con.close()

    if upserted:
        status = "success"
        error = None
    elif row_errors:
        status = "error"
        error = "all_rows_failed_or_invalid"
    else:
        status = "error"
        error = "empty_csv_no_payment_rows"

    return {
        "status": status,
        "source": "erp_csv",
        "files": [str(f) for f in files],
        "payment_ids": upserted,
        "count": len(upserted),
        "row_errors": row_errors,
        "error": error,
        "needs_review": len(upserted) > 0 or len(row_errors) > 0,
    }


def load_hubspot_gap_fixture() -> list[dict[str, Any]]:
    if not SAMPLE_HUBSPOT_GAPS.is_file():
        return []
    return json.loads(SAMPLE_HUBSPOT_GAPS.read_text(encoding="utf-8"))


def triage_hubspot_gaps(
    *,
    customer_ids: list[str] | None = None,
    use_live_hubspot: bool = True,
) -> dict[str, Any]:
    """Detect sold-vs-invoiced gaps via live HubSpot compare or offline fixture."""
    from data_plane import repository as repo

    gaps_out: list[dict[str, Any]] = []
    modes_seen: set[str] = set()

    fixture_rows = load_hubspot_gap_fixture()
    targets = customer_ids or sorted(
        {
            *(str(r.get("customer_id") or "").upper() for r in fixture_rows),
            *{
                str(p.get("customer_id") or "").upper()
                for p in repo.list_payments(unmatched_only=True)
            },
        }
    )
    targets = [t for t in targets if t]

    for cust in targets:
        fixture = next(
            (r for r in fixture_rows if str(r.get("customer_id") or "").upper() == cust),
            None,
        )
        company_id = str((fixture or {}).get("company_id") or "")
        live_used = False
        # Only attempt live HubSpot for non-fixture company ids.
        looks_fixture = company_id.startswith("hs-fixture") or company_id.startswith("fixture")
        if use_live_hubspot and company_id and not looks_fixture:
            from finance_ops.tools.hubspot_tools import compare_sold_contracted_invoiced

            cmp_out = compare_sold_contracted_invoiced(
                customer_id=cust, company_id=company_id
            )
            if cmp_out.get("status") == "success" and cmp_out.get("hubspot_status") == "success":
                live_used = True
                modes_seen.add("live_hubspot")
                if cmp_out.get("gaps"):
                    gaps_out.append(
                        {
                            "customer_id": cust,
                            "company_id": company_id,
                            "sold": cmp_out.get("sold"),
                            "invoiced_total": cmp_out.get("invoiced_total"),
                            "open_invoiced": cmp_out.get("open_invoiced"),
                            "gaps": cmp_out.get("gaps"),
                            "source": "hubspot:live",
                            "needs_review": True,
                        }
                    )
                continue

        invoices = list(repo.list_invoices(customer_id=cust, open_only=False))
        invoiced = sum(float(i.get("amount") or 0) for i in invoices)
        open_invoiced = sum(
            float(i.get("amount") or 0)
            for i in invoices
            if str(i.get("status")) in {"open", "past_due"}
        )
        sold = float((fixture or {}).get("sold") or 0)
        detected: list[str] = []
        if sold and invoiced and abs(sold - invoiced) > max(500.0, 0.05 * max(sold, invoiced)):
            detected.append("sold_vs_invoiced")
        if sold and open_invoiced > sold * 1.05:
            detected.append("open_ar_over_sold")
        if detected or (fixture and sold and not invoices):
            if not detected and fixture and sold and not invoices:
                detected = ["sold_without_invoices"]
            modes_seen.add("fixture")
            gaps_out.append(
                {
                    "customer_id": cust,
                    "company_id": company_id or None,
                    "sold": sold,
                    "invoiced_total": invoiced,
                    "open_invoiced": open_invoiced,
                    "gaps": detected,
                    "source": (fixture or {}).get("source") or "fixture:hubspot_gaps",
                    "needs_review": True,
                    "live_attempted": bool(
                        use_live_hubspot and company_id and not looks_fixture and not live_used
                    ),
                }
            )

    if modes_seen == {"live_hubspot"}:
        mode = "live_hubspot"
    elif modes_seen == {"fixture"}:
        mode = "fixture"
    elif modes_seen:
        mode = "mixed"
    else:
        mode = "none"

    return {
        "status": "success",
        "mode": mode,
        "gap_count": len(gaps_out),
        "gaps": gaps_out,
        "needs_review": len(gaps_out) > 0,
        "repo_root": str(REPO_ROOT),
    }


def _is_hitl_ready(candidate: dict[str, Any] | None, *, min_score: float) -> bool:
    if not candidate:
        return False
    score = float(candidate.get("score") or 0)
    reasons = set(candidate.get("reasons") or [])
    if score < min_score:
        return False
    # Amount gate is mandatory — blocks invoice+PO false positives at score 1.1.
    return REQUIRED_HITL_REASONS.issubset(reasons)


def triage_unmatched_payments(
    *,
    payment_ids: list[str] | None = None,
    min_score: float = HIGH_CONFIDENCE_SCORE,
) -> dict[str, Any]:
    """Suggest invoice matches for unmatched cash (no apply / no HITL).

    Uses batch scoring (one invoice preload) so bulk feeds stay O(customers) I/O.
    """
    from data_plane import repository as repo
    from finance_ops.ar_queue.application.scoring import score_payments_batch

    if payment_ids:
        ids = [p.strip().upper() for p in payment_ids if p.strip()]
        payments = []
        missing: set[str] = set()
        for pid in ids:
            row = repo.get_payment(pid)
            if row:
                payments.append(row)
            else:
                missing.add(pid)
    else:
        payments = repo.list_payments(unmatched_only=True)
        ids = [
            str(p.get("payment_id") or "").upper()
            for p in payments
            if p.get("payment_id")
        ]
        missing = set()

    scored_map = score_payments_batch(payments)
    suggestions: list[dict[str, Any]] = []
    ready_for_hitl: list[dict[str, Any]] = []
    for pid in ids:
        if pid in missing:
            suggestions.append(
                {"payment_id": pid, "status": "not_found", "error": None}
            )
            continue
        out = scored_map.get(pid)
        if not out or out.get("status") != "success":
            suggestions.append(
                {
                    "payment_id": pid,
                    "status": (out or {}).get("status") or "not_found",
                    "error": (out or {}).get("error"),
                }
            )
            continue
        rec = out.get("recommendation")
        cands = out.get("candidates") or []
        top = cands[0] if cands else None
        score = float((top or {}).get("score") or 0)
        reasons = list((top or {}).get("reasons") or [])
        item = {
            "payment_id": pid,
            "recommendation": rec,
            "top_score": score,
            "top_reasons": reasons,
            "candidate_count": len(cands),
            "needs_review": True,
        }
        suggestions.append(item)
        if rec and _is_hitl_ready(top, min_score=min_score):
            ready_for_hitl.append(
                {
                    "payment_id": pid,
                    "invoice_id": rec,
                    "score": score,
                    "reasons": reasons,
                }
            )

    return {
        "status": "success",
        "payment_count": len(ids),
        "suggestions": suggestions,
        "ready_for_hitl": ready_for_hitl,
        "ready_count": len(ready_for_hitl),
        "needs_review": len(ids) > 0,
    }


def _pending_cash_app_keys(store: Any) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for item in store.list("pending"):
        if item.kind not in {"cash_app_match", "cash_app_escalate", "payment_match", "cash_app"}:
            continue
        payload = item.payload or {}
        pid = str(payload.get("payment_id") or "").upper()
        inv = str(payload.get("invoice_id") or "").upper()
        if pid and inv:
            keys.add((pid, inv))
    return keys


def open_hitl_for_ready(
    ready: list[dict[str, Any]],
    *,
    notify_slack: bool = False,
    limit: int = 10,
) -> dict[str, Any]:
    """Open request_cash_app_approval for high-confidence suggestions (still human-gated).

    Skips payment/invoice pairs that already have a pending cash-app approval.
    """
    from finance_ops.runtime.hitl import DEFAULT_STORE
    from finance_ops.tools.payment_tools import request_cash_app_approval

    existing = _pending_cash_app_keys(DEFAULT_STORE)
    opened: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for item in ready[:limit]:
        pid = str(item.get("payment_id") or "").upper()
        inv = str(item.get("invoice_id") or "").upper()
        if not pid or not inv:
            continue
        if (pid, inv) in existing:
            skipped.append(
                {
                    "payment_id": pid,
                    "invoice_id": inv,
                    "reason": "pending_approval_exists",
                }
            )
            continue
        out = request_cash_app_approval(
            pid, invoice_id=inv, notify_slack=notify_slack
        )
        approval_id = (out.get("approval") or {}).get("approval_id")
        opened.append(
            {
                "payment_id": pid,
                "invoice_id": inv,
                "status": out.get("status"),
                "approval_id": approval_id,
            }
        )
        if out.get("status") == "pending" and approval_id:
            existing.add((pid, inv))
    return {
        "status": "success",
        "opened_count": len(opened),
        "skipped_count": len(skipped),
        "opened": opened,
        "skipped": skipped,
        "needs_review": any(o.get("status") == "pending" for o in opened),
    }
