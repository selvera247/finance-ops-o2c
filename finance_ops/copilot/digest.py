"""Optional ranked Copilot exception digest — off by default (alert fatigue).

Generates a digest payload from the ranked queue with precision/quality gates.
Optional Slack/email send stubs behind a second flag (never on by default).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from finance_ops.copilot import service as copilot_service
from finance_ops.copilot.config import (
    digest_enabled,
    digest_exclude_insufficient,
    digest_max_items,
    digest_min_confidence,
    digest_send_enabled,
)
from finance_ops.lib.paths import REPO_ROOT

ConfidenceBand = Literal["high", "medium", "low", "insufficient"]

_BAND_RANK = {"insufficient": 0, "low": 1, "medium": 2, "high": 3}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _meets_min_confidence(band: str | None, minimum: str) -> bool:
    got = _BAND_RANK.get((band or "insufficient").lower(), 0)
    need = _BAND_RANK.get(minimum.lower(), 2)
    return got >= need


def build_digest_payload(
    *,
    limit: int | None = None,
    min_confidence: str | None = None,
    exclude_insufficient: bool | None = None,
    sync_first: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Build digest payload. Returns ``enabled=False`` unless configured or force.

    Quality gates (defaults):
    - drop ``insufficient_data`` / ``confidence_band=insufficient``
    - require confidence >= COPILOT_DIGEST_MIN_CONFIDENCE (default medium)
    """
    enabled = digest_enabled() or force
    min_conf = (min_confidence or digest_min_confidence()).lower()
    drop_insuff = (
        digest_exclude_insufficient()
        if exclude_insufficient is None
        else exclude_insufficient
    )
    max_items = limit if limit is not None else digest_max_items()

    if not enabled:
        return {
            "status": "disabled",
            "enabled": False,
            "reason": "COPILOT_DIGEST_ENABLED is off (default) — avoid alert fatigue",
            "generated_at": _now(),
            "items": [],
            "excluded": [],
            "gates": {
                "min_confidence": min_conf,
                "exclude_insufficient": drop_insuff,
                "max_items": max_items,
            },
        }

    # detail=full only for digest (needs lines/summary); workbench uses summary.
    queue = copilot_service.list_queue(
        status="open",
        lane="cash_app",
        limit=max(max_items * 5, 50),
        sync_first=sync_first,
        detail="full",
    )
    cases = list(queue.get("cases") or [])
    items: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for case in cases:
        hyp = case.get("hypothesis") or {}
        band = hyp.get("confidence_band") or case.get("confidence_band")
        insuff = bool(
            hyp.get("insufficient_data")
            if isinstance(hyp, dict)
            else case.get("insufficient_data")
        )
        reasons: list[str] = []
        if drop_insuff and (insuff or band == "insufficient"):
            reasons.append("insufficient_data")
        if not _meets_min_confidence(band, min_conf):
            reasons.append(f"below_min_confidence:{min_conf}")
        if reasons:
            excluded.append(
                {
                    "case_id": case.get("case_id"),
                    "customer_id": case.get("customer_id"),
                    "payment_id": case.get("payment_id"),
                    "confidence_band": band,
                    "reasons": reasons,
                }
            )
            continue
        items.append(
            {
                "case_id": case.get("case_id"),
                "customer_id": case.get("customer_id"),
                "payment_id": case.get("payment_id"),
                "amount": case.get("amount"),
                "currency": case.get("currency"),
                "aging_days": case.get("aging_days"),
                "status": case.get("status"),
                "confidence_band": band,
                "match_score": case.get("match_score"),
                "recommended_invoice_id": case.get("recommended_invoice_id"),
                "lines": hyp.get("lines") or [] if isinstance(hyp, dict) else [],
                "summary": (case.get("summary") or {}).get("summary"),
            }
        )
        if len(items) >= max_items:
            break

    return {
        "status": "success",
        "enabled": True,
        "generated_at": _now(),
        "title": "Copilot cash-app exception digest",
        "count": len(items),
        "excluded_count": len(excluded),
        "items": items,
        "excluded": excluded,
        "gates": {
            "min_confidence": min_conf,
            "exclude_insufficient": drop_insuff,
            "max_items": max_items,
        },
        "mode": queue.get("mode"),
        "prototype_mode": queue.get("prototype_mode"),
    }


def render_digest_text(payload: dict[str, Any]) -> str:
    if not payload.get("enabled"):
        return (
            f"[digest disabled] {payload.get('reason')}\n"
            f"generated_at={payload.get('generated_at')}"
        )
    lines = [
        payload.get("title") or "Copilot digest",
        f"generated_at={payload.get('generated_at')} count={payload.get('count')}",
        f"gates={payload.get('gates')}",
        "",
    ]
    for i, item in enumerate(payload.get("items") or [], 1):
        lines.append(
            f"{i}. {item.get('case_id')} customer={item.get('customer_id')} "
            f"payment={item.get('payment_id')} amount={item.get('amount')} "
            f"aging={item.get('aging_days')}d band={item.get('confidence_band')}"
        )
        if item.get("recommended_invoice_id") or item.get("lines"):
            inv = item.get("recommended_invoice_id")
            if not inv and item.get("lines"):
                inv = item["lines"][0].get("invoice_id")
            lines.append(f"   → candidate {inv}")
    if not payload.get("items"):
        lines.append("(no cases passed quality gates)")
    return "\n".join(lines)


def stub_send_digest(
    payload: dict[str, Any],
    *,
    force_send: bool = False,
) -> dict[str, Any]:
    """Optional send stub — never delivers unless COPILOT_DIGEST_SEND=1 or force.

    Writes a local artifact under ``.copilot/digests/`` so operators can inspect.
    Slack/email are stubs only (no network send in MVP).
    """
    send_on = digest_send_enabled() or force_send
    text = render_digest_text(payload)
    out_dir = REPO_ROOT / ".copilot" / "digests"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = out_dir / f"digest-{stamp}.json"
    txt_path = out_dir / f"digest-{stamp}.txt"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    txt_path.write_text(text, encoding="utf-8")

    channels: dict[str, Any] = {
        "file_json": str(json_path),
        "file_txt": str(txt_path),
        "slack": {"sent": False, "stub": True},
        "email": {"sent": False, "stub": True},
    }
    if send_on and payload.get("enabled"):
        # Stubs only — record intent; do not POST to Slack/SMTP in MVP.
        slack_url = (os.getenv("SLACK_WEBHOOK_URL") or "").strip()
        channels["slack"] = {
            "sent": False,
            "stub": True,
            "would_post": bool(slack_url),
            "webhook_configured": bool(slack_url),
            "note": "MVP stub — set COPILOT_DIGEST_SEND=1 records intent only; no HTTP post",
        }
        mail_to = (os.getenv("COPILOT_DIGEST_EMAIL_TO") or "").strip()
        channels["email"] = {
            "sent": False,
            "stub": True,
            "would_send_to": mail_to or None,
            "note": "MVP stub — no SMTP; outbound collections email remains out of scope",
        }
    return {
        "status": "success" if payload.get("enabled") else "disabled",
        "send_enabled": send_on,
        "channels": channels,
        "payload_count": payload.get("count"),
    }


def run_digest(
    *,
    sync_first: bool = False,
    force: bool = False,
    send: bool = False,
    limit: int | None = None,
    min_confidence: str | None = None,
) -> dict[str, Any]:
    """Entry point for CLI / scheduled job."""
    payload = build_digest_payload(
        sync_first=sync_first,
        force=force,
        limit=limit,
        min_confidence=min_confidence,
    )
    send_result = None
    if send or digest_send_enabled():
        send_result = stub_send_digest(payload, force_send=send)
    elif payload.get("enabled"):
        # Always persist artifact when digest is enabled even without send flag.
        send_result = stub_send_digest(payload, force_send=False)
    return {
        "status": payload.get("status"),
        "digest": payload,
        "delivery": send_result,
        "text": render_digest_text(payload),
    }
